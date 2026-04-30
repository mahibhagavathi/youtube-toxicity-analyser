import streamlit as st
import pandas as pd
import re
from googleapiclient.discovery import build

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YT Comment Toxicity Analyser",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* Base */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Hide default streamlit header decoration */
#MainMenu, footer, header { visibility: hidden; }

/* Page background */
.stApp {
    background-color: #0a0a0f;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #111118;
    border-right: 1px solid #1e1e2e;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}

/* App header */
.app-header {
    padding: 2rem 0 1.5rem 0;
    border-bottom: 1px solid #1e1e2e;
    margin-bottom: 2rem;
}
.app-title {
    font-size: 2rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin: 0;
}
.app-subtitle {
    font-size: 0.9rem;
    color: #6b6b80;
    margin-top: 0.3rem;
}

/* Input card */
.input-card {
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 2rem;
}

/* Metric cards */
.metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
}
.metric-card {
    flex: 1;
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
}
.metric-card .label {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6b6b80;
    margin-bottom: 0.5rem;
}
.metric-card .value {
    font-size: 2rem;
    font-weight: 700;
    color: #ffffff;
    line-height: 1;
}
.metric-card.toxic   { border-top: 3px solid #e53935; }
.metric-card.border  { border-top: 3px solid #fb8c00; }
.metric-card.normal  { border-top: 3px solid #43a047; }
.metric-card.total   { border-top: 3px solid #5c6bc0; }

/* Section headers */
.section-title {
    font-size: 1rem;
    font-weight: 600;
    color: #c0c0d0;
    letter-spacing: 0.04em;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Score bar */
.score-bar-wrap {
    background: #1a1a24;
    border-radius: 6px;
    height: 6px;
    overflow: hidden;
    margin: 4px 0 12px;
}
.score-bar-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, #5c6bc0, #e53935);
}
.score-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2px;
}
.score-label { font-size: 0.82rem; color: #a0a0b8; }
.score-pct   { font-family: 'DM Mono', monospace; font-size: 0.82rem; color: #ffffff; }

/* Comment cards */
.comment-card {
    background: #111118;
    border: 1px solid #1e1e2e;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    position: relative;
}
.comment-card.toxic-card     { border-left: 3px solid #e53935; }
.comment-card.borderline-card{ border-left: 3px solid #fb8c00; }
.comment-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 4px;
    margin-bottom: 0.6rem;
}
.badge-toxic      { background: rgba(229,57,53,0.15); color: #e57373; }
.badge-borderline { background: rgba(251,140,0,0.15); color: #ffb74d; }
.comment-text { font-size: 0.88rem; color: #c8c8d8; line-height: 1.55; }
.comment-score {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #6b6b80;
    margin-top: 0.5rem;
}
.comment-type-tag {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    color: #5c6bc0;
    background: rgba(92,107,192,0.12);
    border-radius: 4px;
    padding: 1px 6px;
    margin-left: 6px;
}

/* Sidebar video card */
.video-meta-section {
    margin-top: 0.75rem;
}
.meta-item {
    display: flex;
    flex-direction: column;
    margin-bottom: 0.85rem;
}
.meta-key {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6b6b80;
    margin-bottom: 2px;
}
.meta-val {
    font-size: 0.9rem;
    font-weight: 500;
    color: #e0e0f0;
    line-height: 1.3;
}

/* Divider */
.thin-divider {
    border: none;
    border-top: 1px solid #1e1e2e;
    margin: 1.5rem 0;
}

/* Streamlit button override */
.stButton > button {
    background: #5c6bc0;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
    font-size: 0.9rem;
    padding: 0.55rem 2rem;
    transition: background 0.2s;
}
.stButton > button:hover { background: #7986cb; }

/* Streamlit text input */
div[data-testid="stTextInput"] input {
    background: #1a1a24;
    border: 1px solid #2a2a3a;
    border-radius: 8px;
    color: #e0e0f0;
    font-family: 'DM Sans', sans-serif;
}

/* Streamlit selectbox / slider labels */
label { color: #a0a0b8 !important; font-size: 0.82rem !important; }

/* expander */
details summary { color: #a0a0b8; }
</style>
""", unsafe_allow_html=True)

# ── SECRETS ──────────────────────────────────────────────────────────────────
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except Exception:
    st.error("Missing YOUTUBE_API_KEY in Streamlit secrets.")
    st.stop()

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
TOXICITY_META = {
    "toxicity":        ("☠️ Toxicity",        "General harmful or rude content"),
    "severe_toxicity": ("💀 Severe Toxicity",  "Extremely hateful or violent language"),
    "obscene":         ("🤬 Obscene",          "Heavy profanity or vulgar language"),
    "threat":          ("⚠️ Threat",           "Direct threats of harm or violence"),
    "insult":          ("👊 Insult",           "Personal attacks or name-calling"),
    "identity_attack": ("🎯 Identity Attack",  "Hate speech targeting race, gender, religion etc."),
}
TYPE_COLS = list(TOXICITY_META.keys())

# ── HELPERS ───────────────────────────────────────────────────────────────────
def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

def format_date(raw):
    """Turn '2023-04-15T...' → 'April 15, 2023'."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw[:10] if raw else "Unknown"

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
        "published": snippet.get("publishedAt", ""),
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
    all_scores = {}
    for i in range(0, len(comments), 64):
        batch = comments[i:i+64]
        batch_scores = model.predict(batch)
        for k, v in batch_scores.items():
            all_scores.setdefault(k, []).extend(v.tolist() if hasattr(v, "tolist") else list(v))
    df = pd.DataFrame(all_scores)
    df.insert(0, "comment", comments)
    def label(row):
        if row["toxicity"] >= 0.7: return "toxic"
        if row["toxicity"] >= 0.4: return "borderline"
        return "normal"
    df["label"] = df.apply(label, axis=1)
    return df

def score_bar_html(score, color="#e53935"):
    pct = score * 100
    return f"""
    <div class="score-row">
        <span class="score-label">{{label}}</span>
        <span class="score-pct">{{pct:.0f}}%</span>
    </div>
    <div class="score-bar-wrap">
        <div class="score-bar-fill" style="width:{pct:.1f}%; background:{color};"></div>
    </div>
    """

def color_for_score(score):
    if score >= 0.7: return "#e53935"
    if score >= 0.4: return "#fb8c00"
    return "#43a047"

# ── LAYOUT ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div class="app-title">🔬 YouTube Comment Analyser</div>
    <div class="app-subtitle">Detect toxic, borderline, and harmful comments using AI</div>
</div>
""", unsafe_allow_html=True)

# Input section
with st.container():
    url = st.text_input("", placeholder="Paste a YouTube URL — e.g. https://youtube.com/watch?v=...")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        order = st.selectbox("Sort comments by", ["Top (Relevance)", "Newest"])
    with col2:
        max_comments = st.slider("Number of comments to analyse", 20, 300, 100, step=10)
    with col3:
        st.markdown("<div style='margin-top:1.85rem'></div>", unsafe_allow_html=True)
        run = st.button("Analyse →", type="primary", use_container_width=True)

order_val = "relevance" if "Relevance" in order else "time"

if run:
    video_id = extract_video_id(url)
    if not video_id:
        st.error("⚠️ That doesn't look like a valid YouTube URL. Please try again.")
        st.stop()

    # ── Video info → sidebar ──────────────────────────────────────────────────
    with st.spinner("Fetching video info…"):
        info = fetch_video_info(YOUTUBE_API_KEY, video_id)

    if info:
        with st.sidebar:
            if info["thumbnail"]:
                st.image(info["thumbnail"], use_container_width=True)

            st.markdown(f"""
            <div class="video-meta-section">
                <div class="meta-item">
                    <span class="meta-key">Video Title</span>
                    <span class="meta-val">{info['title']}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-key">Channel</span>
                    <span class="meta-val">{info['channel']}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-key">Upload Date</span>
                    <span class="meta-val">{format_date(info['published'])}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Fetch comments ────────────────────────────────────────────────────────
    with st.spinner("Fetching comments…"):
        comments = fetch_comments(YOUTUBE_API_KEY, video_id, order_val, max_comments)
    if not comments:
        st.warning("No comments found for this video.")
        st.stop()

    # ── Analyse ───────────────────────────────────────────────────────────────
    with st.spinner("Scoring comments with AI…"):
        df = analyse_comments(tuple(comments))

    toxic      = df[df["label"] == "toxic"]
    borderline = df[df["label"] == "borderline"]
    normal     = df[df["label"] == "normal"]

    # ── METRICS ───────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card total">
            <div class="label">Total Analysed</div>
            <div class="value">{len(df)}</div>
        </div>
        <div class="metric-card toxic">
            <div class="label">🔴 Toxic</div>
            <div class="value">{len(toxic)}</div>
        </div>
        <div class="metric-card border">
            <div class="label">🟠 Borderline</div>
            <div class="value">{len(borderline)}</div>
        </div>
        <div class="metric-card normal">
            <div class="label">🟢 Normal</div>
            <div class="value">{len(normal)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── CHARTS ────────────────────────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-title">📊 Sentiment Breakdown</div>', unsafe_allow_html=True)
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        labels_  = ["Normal", "Borderline", "Toxic"]
        counts_  = [len(normal), len(borderline), len(toxic)]
        colors_  = ["#43a047", "#fb8c00", "#e53935"]
        fig, ax  = plt.subplots(figsize=(5, 3.2))
        bars     = ax.barh(labels_, counts_, color=colors_, height=0.5, edgecolor="none")
        ax.bar_label(bars, padding=6, fontsize=11, fontweight="bold", color="white",
                     fontfamily="monospace")
        ax.set_xlabel("Comments", color="#6b6b80", fontsize=9)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(colors="#a0a0b8", left=False)
        ax.set_facecolor("#0a0a0f")
        fig.patch.set_facecolor("#0a0a0f")
        ax.xaxis.label.set_color("#6b6b80")
        ax.set_xlim(0, max(counts_) * 1.25 or 1)
        ax.grid(axis="x", color="#1e1e2e", linewidth=0.8)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with right:
        st.markdown('<div class="section-title">🔬 Toxicity Types — Average Score</div>', unsafe_allow_html=True)
        avg = df[TYPE_COLS].mean()
        for col in TYPE_COLS:
            emoji_label, explanation = TOXICITY_META[col]
            score = avg[col]
            clr   = color_for_score(score)
            st.markdown(f"""
            <div style="margin-bottom:0.9rem;">
                <div class="score-row">
                    <span class="score-label">{emoji_label} &nbsp;<span style="color:#555570;font-size:0.75rem">{explanation}</span></span>
                    <span class="score-pct" style="color:{clr}">{score:.0%}</span>
                </div>
                <div class="score-bar-wrap">
                    <div class="score-bar-fill" style="width:{score*100:.1f}%; background:{clr};"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<hr class="thin-divider">', unsafe_allow_html=True)

    # ── TOP TOXIC COMMENTS ────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🚨 Top Comments to Review</div>', unsafe_allow_html=True)
    st.caption("Ranked by toxicity score — these should be reviewed for moderation")

    if toxic.empty and borderline.empty:
        st.success("✅ No toxic or borderline comments found!")
    else:
        top = (pd.concat([toxic, borderline])
               .sort_values("toxicity", ascending=False)
               .head(10))

        for _, row in top.iterrows():
            lbl     = row["label"]
            score   = row["toxicity"]
            dom     = row[TYPE_COLS].idxmax()
            e_label, _ = TOXICITY_META[dom]
            card_cls  = "toxic-card" if lbl == "toxic" else "borderline-card"
            badge_cls = "badge-toxic" if lbl == "toxic" else "badge-borderline"
            badge_txt = "🔴 Toxic" if lbl == "toxic" else "🟠 Borderline"

            st.markdown(f"""
            <div class="comment-card {card_cls}">
                <span class="comment-badge {badge_cls}">{badge_txt}</span>
                <span class="comment-type-tag">{e_label}</span>
                <div class="comment-text">{row['comment']}</div>
                <div class="comment-score">Toxicity score: {score:.0%}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<hr class="thin-divider">', unsafe_allow_html=True)

    # ── ALL COMMENTS TABLE ────────────────────────────────────────────────────
    with st.expander("📋 View all comments with scores"):
        display = (df[["comment", "label", "toxicity", "insult", "obscene", "threat", "identity_attack"]]
                   .sort_values("toxicity", ascending=False)
                   .copy())
        fmt_cols = ["toxicity", "insult", "obscene", "threat", "identity_attack"]
        st.dataframe(
            display.style.format({c: "{:.0%}" for c in fmt_cols}),
            use_container_width=True,
            hide_index=True,
        )
