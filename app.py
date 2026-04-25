import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re
from googleapiclient.discovery import build
from detoxify import Detoxify

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Comment Toxicity Analyser",
    page_icon="🔍",
    layout="centered"
)

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("🔍 YouTube Comment Toxicity Analyser")
st.markdown("Paste any YouTube video link to analyse its top 200 comments for toxic language. Created by Mahitha Bhagavathi.")
st.divider()

# ── Helper: extract video ID from URL ────────────────────────────────────────
def extract_video_id(url):
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# ── Helper: fetch comments ────────────────────────────────────────────────────
def fetch_comments(api_key, video_id, max_comments=200):
    youtube = build("youtube", "v3", developerKey=api_key)
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            order="relevance",
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

# ── API key from Streamlit secrets ────────────────────────────────────────────
try:
    api_key = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    st.error("⚠️ API key not found. Please add YOUTUBE_API_KEY to your Streamlit secrets.")
    st.stop()

# ── Input ─────────────────────────────────────────────────────────────────────
url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...")

analyse_btn = st.button("Analyse Comments", type="primary")

# ── Main logic ────────────────────────────────────────────────────────────────
if analyse_btn:
    if not url.strip():
        st.warning("Please enter a YouTube URL.")
        st.stop()

    video_id = extract_video_id(url)
    if not video_id:
        st.error("Couldn't extract a valid video ID from that URL. Please check the link.")
        st.stop()

    # Fetch comments
    with st.spinner("Fetching up to 200 comments from YouTube..."):
        try:
            comments = fetch_comments(api_key, video_id)
        except Exception as e:
            st.error(f"YouTube API error: {e}")
            st.stop()

    if not comments:
        st.warning("No comments found for this video.")
        st.stop()

    # Run Detoxify
    with st.spinner(f"Analysing {len(comments)} comments for toxicity..."):
        model = Detoxify('original')
        results = model.predict(comments)

    # Build dataframe
    df = pd.DataFrame(comments, columns=["comment"])
    df["toxicity"]        = results["toxicity"]
    df["insult"]          = results["insult"]
    df["threat"]          = results["threat"]
    df["obscene"]         = results["obscene"]
    df["identity_attack"] = results["identity_attack"]
    df["toxic"]           = df["toxicity"] > 0.5

    # ── Results ──────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Results")

    total     = len(df)
    toxic_cnt = df["toxic"].sum()
    rate      = round((toxic_cnt / total) * 100, 1)

    col1, col2, col3 = st.columns(3)
    col1.metric("Comments Analysed", total)
    col2.metric("Toxic Comments",    toxic_cnt)
    col3.metric("Toxicity Rate",     f"{rate}%")

    st.divider()

    # Chart 1 — Toxic vs Normal
    st.subheader("Toxic vs Normal Comments")
    fig1, ax1 = plt.subplots(figsize=(5, 3))
    counts = df["toxic"].value_counts()
    labels = ["Normal" if not k else "Toxic" for k in counts.index]
    colors = ["#4CAF50" if l == "Normal" else "#E53935" for l in labels]
    ax1.bar(labels, counts.values, color=colors)
    ax1.set_ylabel("Number of Comments")
    ax1.set_title("Toxic vs Normal Comments")
    st.pyplot(fig1)

    st.divider()

    # Chart 2 — Abuse category breakdown
    st.subheader("Abuse Category Breakdown")
    abuse_types = ["insult", "threat", "obscene", "identity_attack"]
    avg_scores  = df[abuse_types].mean()
    fig2, ax2 = plt.subplots(figsize=(6, 3))
    bars = ax2.bar(
        [c.replace("_", " ").title() for c in abuse_types],
        avg_scores.values,
        color=["#FF7043", "#AB47BC", "#42A5F5", "#26A69A"]
    )
    ax2.set_ylabel("Average Score")
    ax2.set_title("Average Abuse Scores Across All Comments")
    ax2.set_ylim(0, max(avg_scores.values) * 1.3 + 0.01)
    for bar, val in zip(bars, avg_scores.values):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                 f"{val:.3f}", ha="center", va="bottom", fontsize=9)
    st.pyplot(fig2)

    st.divider()

    # Top 10 most toxic comments
    st.subheader("🚨 Most Toxic Comments")
    st.caption("These are the comments with the highest toxicity score.")
    top_toxic = (
        df.sort_values("toxicity", ascending=False)
        [["comment", "toxicity"]]
        .head(10)
        .reset_index(drop=True)
    )
    top_toxic.index += 1
    top_toxic["toxicity"] = top_toxic["toxicity"].apply(lambda x: f"{x:.2%}")
    st.dataframe(top_toxic, use_container_width=True)

    st.divider()
    st.caption("Built by blmahitha@gmail.com · Powered by YouTube Data API + Detoxify")
