import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
import json
import concurrent.futures
from googleapiclient.discovery import build
import google.generativeai as genai
from wordcloud import WordCloud

# ── CONFIG ─────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Comment Intelligence Analyser",
    page_icon="🧠",
    layout="centered"
)

st.title("🧠 YouTube Comment Intelligence Analyser")
st.markdown("Analyse YouTube comments using AI for sentiment, toxicity, and themes.")
st.divider()

# ── LOAD KEYS ──────────────────────────────────────────
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Missing API keys in Streamlit secrets.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ── HELPERS ────────────────────────────────────────────
def extract_video_id(url):
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"
    ]
    for p in patterns:
        match = re.search(p, url)
        if match:
            return match.group(1)
    return None


def safe_json_parse(text):
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def fetch_comments(api_key, video_id, order, max_comments=200):
    """Cached: won't re-fetch if same video+order is analysed again."""
    youtube = build("youtube", "v3", developerKey=api_key)
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(100, max_comments - len(comments)),
            order=order,
            pageToken=next_page_token
        )
        response = request.execute()
        for item in response.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(text)
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return comments[:max_comments]


def classify_batch(batch):
    """Classify a single batch — called in parallel threads."""
    prompt = f"""
You are a strict JSON generator.
Classify each comment. Return ONLY a valid JSON array. No explanation. No markdown.

Schema:
[
  {{
    "sentiment": "positive | neutral | negative | toxic",
    "toxicity_type": "none | insult | hate | threat | profanity | spam",
    "severity": "low | medium | high",
    "reason": "short reason"
  }}
]

Comments:
{batch}
"""
    fallback = [
        {"sentiment": "neutral", "toxicity_type": "none", "severity": "low", "reason": "parse_error"}
        for _ in batch
    ]
    try:
        response = model.generate_content(prompt)
        parsed = safe_json_parse(response.text)
        if isinstance(parsed, list) and len(parsed) == len(batch):
            return parsed
        return fallback
    except Exception:
        return fallback


@st.cache_data(show_spinner=False)
def classify_comments(comments_tuple):
    """
    Cached + parallelised classification.
    Accepts a tuple (hashable) so st.cache_data works.
    """
    comments = list(comments_tuple)
    batch_size = 20
    batches = [comments[i:i+batch_size] for i in range(0, len(comments), batch_size)]

    results = []
    # Run all batches in parallel (max 5 threads to avoid rate limits)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(classify_batch, b) for b in batches]
        for f in concurrent.futures.as_completed(futures):
            results.extend(f.result())

    # Reorder to match original comment order
    ordered = []
    idx = 0
    for b in batches:
        ordered.extend(results[idx:idx+len(b)])
        idx += len(b)
    return ordered


@st.cache_data(show_spinner=False)
def extract_themes(comments_tuple):
    """Cached theme extraction."""
    comments = list(comments_tuple)
    prompt = f"""
Group these YouTube comments into themes.
Return ONLY valid JSON. No markdown.

Schema:
{{"themes": [{{"name": "string", "percentage": number}}]}}

Comments:
{comments[:100]}
"""
    try:
        response = model.generate_content(prompt)
        parsed = safe_json_parse(response.text)
        if parsed and "themes" in parsed:
            return parsed["themes"]
    except Exception:
        pass
    return []


# ── INPUT ──────────────────────────────────────────────
url = st.text_input("YouTube URL")
order = st.selectbox("Comment Order", ["Top (Relevance)", "Newest"])
order_val = "relevance" if order == "Top (Relevance)" else "time"
max_comments = st.slider("Max comments to analyse", 50, 200, 100, step=50)

if st.button("Analyse", type="primary"):

    video_id = extract_video_id(url)
    if not video_id:
        st.error("Invalid YouTube URL.")
        st.stop()

    # ── STEP 1: Fetch ──────────────────────────────────
    with st.spinner("📥 Fetching comments..."):
        comments = fetch_comments(YOUTUBE_API_KEY, video_id, order_val, max_comments)

    if not comments:
        st.warning("No comments found for this video.")
        st.stop()

    st.info(f"Fetched **{len(comments)}** comments. Running AI analysis in parallel…")

    # ── STEP 2: Classify (parallel + cached) ──────────
    with st.spinner("🤖 Classifying with Gemini (parallel batches)..."):
        analysis = classify_comments(tuple(comments))  # tuple for caching

    df = pd.DataFrame(comments, columns=["comment"])
    analysis_df = pd.DataFrame(analysis)

    # Align lengths if mismatch
    min_len = min(len(df), len(analysis_df))
    df = df.iloc[:min_len]
    analysis_df = analysis_df.iloc[:min_len]

    df = pd.concat([df.reset_index(drop=True), analysis_df.reset_index(drop=True)], axis=1)

    toxic_df = df[df["sentiment"] == "toxic"]
    normal_df = df[df["sentiment"] != "toxic"]

    # ── METRICS ────────────────────────────────────────
    st.subheader("📊 Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Comments", len(df))
    col2.metric("Toxic", len(toxic_df))
    col3.metric("Normal", len(normal_df))

    # ── SENTIMENT CHART ────────────────────────────────
    st.subheader("😐 Sentiment Distribution")
    sentiment_counts = df["sentiment"].value_counts()
    fig, ax = plt.subplots()
    colors = {"positive": "#4CAF50", "neutral": "#9E9E9E", "negative": "#FF9800", "toxic": "#F44336"}
    bar_colors = [colors.get(s, "#888") for s in sentiment_counts.index]
    ax.bar(sentiment_counts.index, sentiment_counts.values, color=bar_colors)
    ax.set_ylabel("Count")
    st.pyplot(fig)

    # ── THEMES ─────────────────────────────────────────
    st.subheader("✨ Comment Themes")
    with st.spinner("Extracting themes..."):
        themes = extract_themes(tuple(normal_df["comment"].tolist()))

    if themes:
        theme_df = pd.DataFrame(themes)
        fig_t, ax_t = plt.subplots()
        ax_t.pie(theme_df["percentage"], labels=theme_df["name"], autopct="%1.0f%%", startangle=90)
        st.pyplot(fig_t)
    else:
        st.write("Could not extract themes.")

    # ── TOXIC BREAKDOWN ────────────────────────────────
    if not toxic_df.empty:
        st.subheader("🚨 Toxic Comment Categories")
        toxic_counts = toxic_df["toxicity_type"].value_counts()
        fig2, ax2 = plt.subplots()
        ax2.bar(toxic_counts.index, toxic_counts.values, color="#F44336")
        ax2.set_ylabel("Count")
        st.pyplot(fig2)

        st.subheader("🔥 Top Toxic Comments")
        st.dataframe(
            toxic_df[["comment", "toxicity_type", "severity", "reason"]].head(10),
            use_container_width=True
        )
    else:
        st.success("🎉 No toxic comments detected!")

    # ── WORD CLOUD ─────────────────────────────────────
    st.subheader("☁️ Word Cloud (Normal Comments)")
    text = " ".join(normal_df["comment"].tolist())
    if text.strip():
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig3, ax3 = plt.subplots(figsize=(10, 5))
        ax3.imshow(wc, interpolation="bilinear")
        ax3.axis("off")
        st.pyplot(fig3)

    st.success("✅ Analysis complete!")
