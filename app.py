import streamlit as st
import pandas as pd
import re
from googleapiclient.discovery import build

st.set_page_config(page_title="YouTube Comment Analyser", page_icon="🧠", layout="wide")
st.title("🧠 YouTube Comment Analyser")

try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    st.error("Missing YOUTUBE_API_KEY in Streamlit secrets.")
    st.stop()

TOXICITY_EXPLANATIONS = {
    "toxicity":            ("☠️ Toxicity",           "General harmful or rude content"),
    "severe_toxicity":     ("💀 Severe Toxicity",     "Extremely hateful or violent language"),
    "obscene":             ("🤬 Obscene",             "Heavy profanity or vulgar language"),
    "threat":              ("⚠️ Threat",              "Direct threats of harm or violence"),
    "insult":              ("👊 Insult",              "Personal attacks or name-calling"),
    "identity_attack":     ("🎯 Identity Attack",     "Hate speech targeting race, gender, religion etc."),
}

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
        "title":     snippet.get("title", "Unknown"),
        "channel":   snippet.get("channelTitle", "Unknown"),
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

@st.cache_resource
def load_model():
    from detoxify import Detoxify
    return Detoxify("original")

@st.cache_data(show_spinner=False)
def analyse_comments(comments_tuple):
    model = load_model()
    comments = list(comments_tuple)
    scores = model.predict(comments)
    df = pd.DataFrame(scores)
    df.insert(0, "comment", comments)
    # label each comment
    def label(row):
        if row["toxicity"] >= 0.7:   return "toxic"
        if row["toxicity"] >= 0.4:   return "borderline"
        return "normal"
    df["label"] = df.apply(label, axis=1)
    return df

def score_bar(score):
    filled = int(score * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"`{bar}` {score:.0%}"

def badge(label):
    return {"toxic": "🔴 Toxic", "borderline": "🟠 Borderline", "normal": "🟢 Normal"}.get(label, label)

# ── UI ──
url = st.text_input("YouTube URL")
col1, col2 = st.columns(2)
order = col1.selectbox("Order", ["Top (Relevance)", "Newest"])
max_comments = col2.slider("Max comments", 20, 300, 100, step=10)
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

    with st.spinner("Loading model & scoring comments..."):
        df = analyse_comments(tuple(comments))

    toxic      = df[df["label"] == "toxic"]
    borderline = df[df["label"] == "borderline"]
    normal     = df[df["label"] == "normal"]

    # ── METRICS ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total",           len(df))
    c2.metric("Toxic 🔴",        len(toxic))
    c3.metric("Borderline 🟠",   len(borderline))
    c4.metric("Normal 🟢",       len(normal))

    st.divider()

    # ── SENTIMENT BREAKDOWN ──
    left, right = st.columns(2)
    with left:
        st.subheader("📊 Sentiment Breakdown")
        import matplotlib.pyplot as plt
        labels  = ["Toxic", "Borderline", "Normal"]
        counts  = [len(toxic), len(borderline), len(normal)]
        colors  = ["#e53935", "#fb8c00", "#43a047"]
        # sort descending
        paired  = sorted(zip(counts, labels, colors), reverse=True)
        counts, labels, colors = zip(*paired)
        fig, ax = plt.subplots(figsize=(5, 3))
        bars = ax.bar(labels, counts, color=colors, edgecolor="none", width=0.5)
        ax.bar_label(bars, padding=3, fontsize=11, fontweight="bold")
        ax.set_ylabel("Comments")
        ax.spines[["top","right"]].set_visible(False)
        ax.set_facecolor("#0e1117")
        fig.patch.set_facecolor("#0e1117")
        ax.tick_params(colors="white")
        ax.yaxis.label.set_color("white")
        st.pyplot(fig)
        plt.close(fig)

    # ── TOXICITY TYPE BREAKDOWN ──
    with right:
        st.subheader("🔬 Toxicity Types")
        type_cols = ["toxicity", "severe_toxicity", "obscene", "threat", "insult", "identity_attack"]
        avg_scores = df[type_cols].mean()
        for col in type_cols:
            emoji_label, explanation = TOXICITY_EXPLANATIONS[col]
            score = avg_scores[col]
            st.markdown(f"**{emoji_label}** — *{explanation}*")
            st.markdown(score_bar(score))

    st.divider()

    # ── TOP COMMENTS TO REMOVE ──
    st.subheader("🚨 Top Comments to Remove")
    st.caption("Ranked by overall toxicity score — these should be reviewed for deletion")

    if toxic.empty and borderline.empty:
        st.success("No toxic or borderline comments found!")
    else:
        top = pd.concat([toxic, borderline]).sort_values("toxicity", ascending=False).head(10)
        for _, row in top.iterrows():
            score = row["toxicity"]
            dominant_type = row[type_cols].idxmax()
            emoji_label, explanation = TOXICITY_EXPLANATIONS[dominant_type]
            with st.container():
                l, r = st.columns([5, 1])
                with l:
                    st.markdown(f"{badge(row['label'])} · **{emoji_label}**")
                    st.write(row["comment"])
                with r:
                    st.markdown(f"### {score:.0%}")
                st.divider()

    # ── ALL COMMENTS ──
    with st.expander("All comments"):
        display = df[["comment", "label", "toxicity", "insult", "obscene", "threat", "identity_attack"]].copy()
        display = display.sort_values("toxicity", ascending=False)
        st.dataframe(display.style.format({c: "{:.0%}" for c in type_cols if c in display.columns}), use_container_width=True)
