import streamlit as st
import pandas as pd
import re
import json
import concurrent.futures
from groq import Groq
from googleapiclient.discovery import build

st.set_page_config(page_title="YouTube Comment Analyser", page_icon="🧠", layout="wide")
st.title("🧠 YouTube Comment Analyser")

try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("Missing API keys in Streamlit secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

def groq_call(prompt):
    res = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return res.choices[0].message.content

@st.cache_data(show_spinner=False)
def fetch_video_info(api_key, video_id):
    youtube = build("youtube", "v3", developerKey=api_key)
    res = youtube.videos().list(part="snippet", id=video_id).execute()
    items = res.get("items", [])
    if not items:
        return None
    snippet = items[0]["snippet"]
    return {
        "title": snippet.get("title", "Unknown"),
        "channel": snippet.get("channelTitle", "Unknown"),
        "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
        "published": snippet.get("publishedAt", "")[:10],
    }

@st.cache_data(show_spinner=False)
def fetch_comments(api_key, video_id, order, max_comments):
    youtube = build("youtube", "v3", developerKey=api_key)
    comments, token = [], None
    while len(comments) < max_comments:
        res = youtube.commentThreads().list(
            part="snippet", videoId=video_id,
            maxResults=min(100, max_comments - len(comments)),
            order=order, pageToken=token
        ).execute()
        for item in res.get("items", []):
            comments.append(item["snippet"]["topLevelComment"]["snippet"]["textDisplay"])
        token = res.get("nextPageToken")
        if not token:
            break
    return comments[:max_comments]

def classify_batch(batch):
    prompt = f"""You are a YouTube comment classifier. Classify each comment honestly, including toxic ones.

For each comment return:
- sentiment: positive, neutral, negative, or toxic
- toxicity_type: none, insult, hate, threat, profanity, or spam
- severity_score: integer 1-10 (1=harmless, 10=extremely toxic). Only score above 5 if truly toxic.
- reason: one short phrase explaining the classification

Rules:
- toxic = insults, slurs, hate speech, threats, heavy swearing at someone
- negative = complaints, criticism, mild rudeness
- positive = praise, support, love, agreement
- neutral = facts, questions, general statements
- Do NOT sanitize. Label toxic comments as toxic with an honest severity_score.
- Non-toxic comments should have severity_score of 1-3.

Return ONLY a raw JSON array, no markdown, no explanation:
[{{"sentiment":"...","toxicity_type":"...","severity_score":5,"reason":"..."}}]

Comments to classify:
{json.dumps(batch)}"""
    fallback = [{"sentiment": "neutral", "toxicity_type": "none", "severity_score": 1, "reason": "error"}] * len(batch)
    try:
        text = groq_call(prompt)
        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start == -1 or end == 0:
            return fallback
        parsed = json.loads(cleaned[start:end])
        if isinstance(parsed, list) and len(parsed) == len(batch):
            return parsed
    except Exception:
        pass
    return fallback

@st.cache_data(show_spinner=False)
def classify_comments(comments_tuple):
    comments = list(comments_tuple)
    batches = [comments[i:i+15] for i in range(0, len(comments), 15)]
    results_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(classify_batch, b): i for i, b in enumerate(batches)}
        for f in concurrent.futures.as_completed(futures):
            results_map[futures[f]] = f.result()
    results = []
    for i in range(len(batches)):
        results.extend(results_map[i])
    return results

@st.cache_data(show_spinner=False)
def extract_themes(comments_tuple):
    comments = list(comments_tuple)[:80]
    prompt = f"""Analyse these YouTube comments and group them into 4-6 themes.
Return ONLY raw JSON, no markdown, no explanation:
{{"themes":[{{"name":"string","percentage":number,"description":"one sentence"}}]}}
Comments: {json.dumps(comments)}"""
    try:
        text = groq_call(prompt)
        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        parsed = json.loads(cleaned[start:end])
        return parsed.get("themes", [])
    except Exception:
        return []

def score_emoji(score):
    if score >= 8: return "🔴"
    if score >= 5: return "🟠"
    return "🟡"

# ── UI ──
url = st.text_input("YouTube URL")
col1, col2 = st.columns(2)
order = col1.selectbox("Order", ["Top (Relevance)", "Newest"])
max_comments = col2.slider("Max comments", 20, 100, 50, step=10)
order_val = "relevance" if "Relevance" in order else "time"

if st.button("Analyse", type="primary"):
    video_id = extract_video_id(url)
    if not video_id:
        st.error("Invalid YouTube URL.")
        st.stop()

    with st.spinner("Fetching video info..."):
        info = fetch_video_info(YOUTUBE_API_KEY, video_id)
    if info:
        with st.sidebar:
            st.image(info["thumbnail"], use_container_width=True)
            st.markdown(f"### {info['title']}")
            st.markdown(f"📺 **{info['channel']}**")
            st.markdown(f"📅 {info['published']}")

    with st.spinner("Fetching comments..."):
        comments = fetch_comments(YOUTUBE_API_KEY, video_id, order_val, max_comments)

    if not comments:
        st.warning("No comments found.")
        st.stop()

    with st.spinner(f"Analysing {len(comments)} comments..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            clf_future = ex.submit(classify_comments, tuple(comments))
            theme_future = ex.submit(extract_themes, tuple(comments))
            analysis = clf_future.result()
            themes = theme_future.result()

    df = pd.DataFrame(comments[:len(analysis)], columns=["comment"])
    df = pd.concat([df, pd.DataFrame(analysis)], axis=1)
    df["severity_score"] = pd.to_numeric(df.get("severity_score", 1), errors="coerce").fillna(1).astype(int)

    toxic = df[df["sentiment"] == "toxic"].copy()
    negative = df[df["sentiment"] == "negative"]
    positive = df[df["sentiment"] == "positive"]

    # ── METRICS ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    c2.metric("Toxic 🔴", len(toxic))
    c3.metric("Negative 🟠", len(negative))
    c4.metric("Positive 🟢", len(positive))

    st.divider()

    # ── SENTIMENT + TOXICITY BREAKDOWN ──
    left, right = st.columns(2)
    with left:
        st.subheader("Sentiment Breakdown")
        st.bar_chart(df["sentiment"].value_counts())
    with right:
        st.subheader("Toxicity Types")
        if not toxic.empty:
            tox_counts = toxic["toxicity_type"].value_counts()
            tox_counts = tox_counts[tox_counts.index != "none"]
            if not tox_counts.empty:
                st.bar_chart(tox_counts)
            else:
                st.info("No specific toxicity types found.")
        else:
            st.success("No toxic comments found!")

    st.divider()

    # ── THEMES ──
    st.subheader("💬 Comment Themes")
    if themes:
        cols = st.columns(len(themes))
        for i, t in enumerate(themes):
            with cols[i]:
                st.metric(t["name"], f"{t['percentage']}%")
                st.caption(t.get("description", ""))
    else:
        st.info("Could not extract themes.")

    st.divider()

    # ── TOP TOXIC COMMENTS (sorted by severity) ──
    if not toxic.empty:
        st.subheader("🚨 Top Comments to Remove")
        st.caption("Sorted by severity score — highest risk first")

        top_toxic = toxic.sort_values("severity_score", ascending=False).head(10)

        for _, row in top_toxic.iterrows():
            score = int(row["severity_score"])
            emoji = score_emoji(score)
            with st.container():
                left_col, right_col = st.columns([5, 1])
                with left_col:
                    st.markdown(f"**{row['toxicity_type'].upper()}** — {row['reason']}")
                    st.write(row["comment"])
                with right_col:
                    st.markdown(f"## {emoji} {score}/10")
                st.divider()

    # ── ALL COMMENTS ──
    with st.expander("All comments"):
        st.dataframe(
            df[["comment", "sentiment", "toxicity_type", "severity_score", "reason"]],
            use_container_width=True
        )
