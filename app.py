import streamlit as st
import pandas as pd
import re
import json
import google.generativeai as genai
from googleapiclient.discovery import build

st.set_page_config(page_title="YouTube Comment Analyser", page_icon="🧠")
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

@st.cache_data(show_spinner=False)
def classify_comments(comments_tuple):
    comments = list(comments_tuple)
    results = []
    for i in range(0, len(comments), 20):
        batch = comments[i:i+20]
        prompt = f"""Classify each comment. Return ONLY a JSON array, no markdown.
Schema: [{{"sentiment":"positive|neutral|negative|toxic","toxicity_type":"none|insult|hate|threat|profanity|spam","reason":"short reason"}}]
Comments: {batch}"""
        try:
            res = model.generate_content(prompt)
            cleaned = res.text.strip().replace("```json","").replace("```","")
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) == len(batch):
                results.extend(parsed)
                continue
        except Exception:
            pass
        results.extend([{"sentiment":"neutral","toxicity_type":"none","reason":"error"}] * len(batch))
    return results

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

    with st.spinner("Fetching comments..."):
        comments = fetch_comments(YOUTUBE_API_KEY, video_id, order_val, max_comments)

    if not comments:
        st.warning("No comments found.")
        st.stop()

    with st.spinner(f"Classifying {len(comments)} comments..."):
        analysis = classify_comments(tuple(comments))

    df = pd.DataFrame(comments[:len(analysis)], columns=["comment"])
    df = pd.concat([df, pd.DataFrame(analysis)], axis=1)

    toxic = df[df["sentiment"] == "toxic"]
    normal = df[df["sentiment"] != "toxic"]

    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", len(df))
    c2.metric("Toxic", len(toxic))
    c3.metric("Normal", len(normal))

    # Sentiment chart
    st.subheader("Sentiment Breakdown")
    counts = df["sentiment"].value_counts()
    st.bar_chart(counts)

    # Toxic table
    if not toxic.empty:
        st.subheader("🚨 Toxic Comments")
        st.dataframe(toxic[["comment","toxicity_type","reason"]], use_container_width=True)
    else:
        st.success("No toxic comments found!")

    # Full results
    with st.expander("All comments"):
        st.dataframe(df[["comment","sentiment","reason"]], use_container_width=True)
