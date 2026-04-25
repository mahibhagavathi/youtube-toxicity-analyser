import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
import json
from googleapiclient.discovery import build
import google.generativeai as genai
from wordcloud import WordCloud

def safe_json_parse(text):
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "")

    try:
        return json.loads(cleaned)
    except:
        return None

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
except:
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


def fetch_comments(api_key, video_id, order, max_comments=200):
    youtube = build("youtube", "v3", developerKey=api_key)
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
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


# ── GEMINI: CLASSIFY COMMENTS ──────────────────────────
def classify_comments(comments):
    results = []

    batch_size = 20
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i+batch_size]

        prompt = f"""
        Classify each comment. Return JSON list.

        Fields:
        sentiment: positive / neutral / negative / toxic
        toxicity_type: none / insult / hate / threat / profanity / spam
        severity: low / medium / high
        reason: short explanation

        Comments:
        {batch}
        """

        response = model.generate_content(prompt)

        try:
            parsed = json.loads(response.text)
            results.extend(parsed)
        except:
            # fallback if parsing fails
            for c in batch:
                results.append({
                    "sentiment": "neutral",
                    "toxicity_type": "none",
                    "severity": "low",
                    "reason": "fallback"
                })

    return results


# ── GEMINI: THEMES ─────────────────────────────────────
def extract_themes(comments):
    prompt = f"""
    Group these comments into themes.

    Return JSON like:
    {{
      "themes": [
        {{"name": "Praise", "percentage": 40}},
        ...
      ]
    }}

    Comments:
    {comments[:100]}
    """

    response = model.generate_content(prompt)

    try:
        return json.loads(response.text)["themes"]
    except:
        return []


# ── INPUT ──────────────────────────────────────────────
url = st.text_input("YouTube URL")

order = st.selectbox(
    "Select Comments",
    ["Top (Relevance)", "Newest"]
)

order_val = "relevance" if order == "Top (Relevance)" else "time"

if st.button("Analyse", type="primary"):

    video_id = extract_video_id(url)
    if not video_id:
        st.error("Invalid URL")
        st.stop()

    # Fetch comments
    with st.spinner("Fetching comments..."):
        comments = fetch_comments(YOUTUBE_API_KEY, video_id, order_val)

    if not comments:
        st.warning("No comments found")
        st.stop()

    # Classify
    with st.spinner("Analyzing with AI..."):
        analysis = classify_comments(comments)

    df = pd.DataFrame(comments, columns=["comment"])
    df = pd.concat([df, pd.DataFrame(analysis)], axis=1)

    # Split
    toxic_df = df[df["sentiment"] == "toxic"]
    normal_df = df[df["sentiment"] != "toxic"]

    # ── METRICS ────────────────────────────────────────
    st.subheader("📊 Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total", len(df))
    col2.metric("Toxic", len(toxic_df))
    col3.metric("Normal", len(normal_df))

    # ── SENTIMENT BREAKDOWN ────────────────────────────
    st.subheader("Sentiment Distribution")
    sentiment_counts = df["sentiment"].value_counts()

    fig, ax = plt.subplots()
    ax.bar(sentiment_counts.index, sentiment_counts.values)
    st.pyplot(fig)

    # ── THEMES ─────────────────────────────────────────
    st.subheader("✨ Normal Comment Themes")

    themes = extract_themes(normal_df["comment"].tolist())

    for t in themes:
        st.write(f"{t['name']} — {t['percentage']}%")

    # ── TOXIC BREAKDOWN ────────────────────────────────
    st.subheader("🚨 Toxic Categories")

    toxic_counts = toxic_df["toxicity_type"].value_counts()

    fig2, ax2 = plt.subplots()
    ax2.bar(toxic_counts.index, toxic_counts.values)
    st.pyplot(fig2)

    # ── TOP TOXIC COMMENTS ─────────────────────────────
    st.subheader("🔥 Most Toxic Comments")

    top_toxic = toxic_df.head(10)[
        ["comment", "toxicity_type", "severity", "reason"]
    ]

    st.dataframe(top_toxic)

    # ── WORD CLOUD ─────────────────────────────────────
    st.subheader("☁️ Word Cloud (Normal Comments)")

    text = " ".join(normal_df["comment"].tolist())

    if text.strip():
        wc = WordCloud(width=800, height=400).generate(text)

        fig3, ax3 = plt.subplots()
        ax3.imshow(wc)
        ax3.axis("off")
        st.pyplot(fig3)

    st.success("Analysis Complete!")
