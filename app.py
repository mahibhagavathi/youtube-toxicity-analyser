import streamlit as st
import pandas as pd
import re
import json
import concurrent.futures
import google.generativeai as genai
from googleapiclient.discovery import build

st.set_page_config(page_title="YouTube Comment Analyser", page_icon="🧠", layout="wide")
st.title("🧠 YouTube Comment Analyser")

try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Missing API keys in Streamlit secrets.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

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
    prompt = f"""You are a strict content moderator. Classify each YouTube comment.

Rules:
- "toxic" = any insult, slur, hate, threat, harassment, heavy profanity, or personal attack
- "negative" = criticism, complaints, or mild rudeness WITHOUT direct attacks
- "positive" = praise, support, agreement
- "neutral" = factual or general statements
- Be aggressive — do NOT let toxic comments pass as neutral or negative

Return ONLY a valid JSON array. No markdown. No explanation. One object per comment.
[{{"sentiment":"positive|neutral|negative|toxic","toxicity_type":"none|insult|hate|threat|profanity|spam","reason":"short reason"}}]

Comments:
{batch}"""
    fallback = [{"sentiment":"neutral","toxicity_type":"none","reason":"error"}] * len(batch)
    try:
        res = model.generate_content(prompt)
        cleaned = res.text.strip().replace("```json","").replace("```","")
        parsed = json.loads(cleaned)
        if isinstance(parsed, list) and len(parsed) == len(batch):
            return parsed
    except Exception:
        pass
    return fallback

@st.cache_data(show_spinner=False)
def classify_comments(comments_tuple):
    comments = list(comments_tuple)
    batches = [comments[i:i+20] for i in range(0, len(comments), 20)]
    results_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
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
Return ONLY valid JSON. No markdown.
{{"themes":[{{"name":"string","percentage":number,"description":"one sentence"}}]}}
Comments: {comments}"""
    try:
        res = model.generate_content(prompt)
        cleaned = res.text.strip().replace("```json","").replace("```","")
        parsed = json.loads(cleaned)
        return parsed.get("themes", [])
    except Exception:
        return []

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

    # Sidebar: video info
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

    # Run classification + themes in parallel
    with st.spinner(f"Analysing {len(comments)} comments..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            clf_future = ex.submit(classify_comments, tuple(comments))
            theme_future = ex.submit(extract_themes, tuple(comments))
            analysis = clf_future.result()
            themes = theme_future.result()

    df = pd.DataFrame(comments[:len(analysis)], columns=["comment"])
    df = pd.concat([df, pd.DataFrame(analysis)], axis=1)

    toxic = df[df["sentiment"] == "toxic"]
    normal = df[df["sentiment"] != "toxic"]

    # ── METRICS ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    c2.metric("Toxic 🔴", len(toxic))
    c3.metric("Negative 🟠", len(df[df["sentiment"]=="negative"]))
    c4.metric("Positive 🟢", len(df[df["sentiment"]=="positive"]))

    st.divider()

    # ── SENTIMENT + TOXICITY BREAKDOWN ──
    left, right = st.columns(2)

    with left:
        st.subheader("Sentiment Breakdown")
        counts = df["sentiment"].value_counts()
        st.bar_chart(counts)

    with right:
        st.subheader("Toxicity Types")
        if not toxic.empty:
            tox_counts = toxic["toxicity_type"].value_counts()
            tox_counts = tox_counts[tox_counts.index != "none"]
            if not tox_counts.empty:
                st.bar_chart(tox_counts)
            else:
                st.info("No specific toxicity types detected.")
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

    # ── TOXIC TABLE ──
    if not toxic.empty:
        st.subheader("🚨 Toxic Comments")
        st.dataframe(toxic[["comment","toxicity_type","reason"]], use_container_width=True)

    # ── ALL COMMENTS ──
    with st.expander("All comments"):
        st.dataframe(df[["comment","sentiment","toxicity_type","reason"]], use_container_width=True)
