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
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}

#MainMenu, footer, header { visibility: hidden; }

/* ── Background ── */
.stApp {
    background-color: #f9f4f4;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1.5px solid #eed9d9;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}

/* ── App header ── */
.app-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.8rem 0 1.4rem;
    border-bottom: 2px solid #f0dada;
    margin-bottom: 2rem;
}
.yt-pill {
    background: #ff0000;
    color: #fff;
    font-size: 1.6rem;
    width: 52px;
    height: 52px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(255,0,0,0.25);
}
.app-title {
    font-size: 1.7rem;
    font-weight: 800;
    color: #1a1a1a;
    letter-spacing: -0.5px;
    line-height: 1.1;
}
.app-subtitle {
    font-size: 0.85rem;
    color: #9b8b8b;
    margin-top: 2px;
    font-weight: 400;
}

/* ── Section label ── */
.section-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #333;
    letter-spacing: 0.01em;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* ── Metric cards ── */
.metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
}
.metric-card {
    flex: 1;
    background: #ffffff;
    border: 1.5px solid #eed9d9;
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
}
.metric-card .m-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #b08f8f;
    margin-bottom: 0.45rem;
}
.metric-card .m-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: #1a1a1a;
    line-height: 1;
}
.metric-card.mc-total   { border-top: 4px solid #c8a0a0; }
.metric-card.mc-toxic   { border-top: 4px solid #e53935; }
.metric-card.mc-border  { border-top: 4px solid #fb8c00; }
.metric-card.mc-normal  { border-top: 4px solid #43a047; }

/* ── Score bars ── */
.score-block { margin-bottom: 1rem; }
.score-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 4px;
}
.score-name  { font-size: 0.83rem; font-weight: 600; color: #2a2a2a; }
.score-desc  { font-size: 0.72rem; color: #b08f8f; margin-left: 5px; font-weight: 400; }
.score-pct   { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; font-weight: 500; color: #2a2a2a; }
.bar-track {
    background: #f0dada;
    border-radius: 99px;
    height: 7px;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 99px;
}

/* ── Comment cards ── */
.comment-card {
    background: #ffffff;
    border: 1.5px solid #eed9d9;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.7rem;
}
.comment-card.cc-toxic      { border-left: 4px solid #e53935; }
.comment-card.cc-borderline { border-left: 4px solid #fb8c00; }
.badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 2px 9px;
    border-radius: 5px;
    margin-right: 6px;
}
.badge-toxic      { background: #fdecea; color: #c62828; }
.badge-borderline { background: #fff3e0; color: #e65100; }
.type-tag {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    color: #c62828;
    background: #fdecea;
    border-radius: 5px;
    padding: 2px 7px;
}
.comment-text {
    font-size: 0.88rem;
    color: #2a2a2a;
    line-height: 1.6;
    margin-top: 0.55rem;
}
.comment-score {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem;
    color: #b08f8f;
    margin-top: 0.5rem;
}

/* ── Sidebar video meta ── */
.meta-block { margin-top: 1rem; }
.meta-item  { margin-bottom: 1rem; }
.meta-key {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #b08f8f;
    margin-bottom: 2px;
}
.meta-val {
    font-size: 0.88rem;
    font-weight: 600;
    color: #1a1a1a;
    line-height: 1.4;
}

/* ── Streamlit overrides ── */
.stButton > button {
    background: #ff0000 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    padding: 0.55rem 1.8rem !important;
    box-shadow: 0 4px 12px rgba(255,0,0,0.2) !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #cc0000 !important;
    box-shadow: 0 6px 18px rgba(255,0,0,0.3) !important;
    transform: translateY(-1px) !important;
}

div[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1.5px solid #eed9d9 !important;
    border-radius: 10px !important;
    color: #1a1a1a !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.9rem !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #ff0000 !important;
    box-shadow: 0 0 0 2px rgba(255,0,0,0.08) !important;
}

label {
    color: #7a5f5f !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}

/* Divider */
.soft-divider {
    border: none;
    border-top: 1.5px solid #f0dada;
    margin: 1.8rem 0;
}

/* Expander */
details summary {
    color: #7a5f5f !important;
    font-weight: 600;
}
details {
    background: #ffffff;
    border-radius: 10px !important;
    padding: 0.5rem;
}

/* Caption */
.stCaption { color: #b08f8f !important; }
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
            all_scores.setdefault(k, []).extend(
                v.tolist() if hasattr(v, "tolist") else list(v)
            )
    df = pd.DataFrame(all_scores)
    df.insert(0, "comment", comments)
    def label(row):
        if row["toxicity"] >= 0.7: return "toxic"
        if row["toxicity"] >= 0.4: return "borderline"
        return "normal"
    df["label"] = df.apply(label, axis=1)
    return df

def bar_color(score):
    if score >= 0.7: return "#e53935"
    if score >= 0.4: return "#fb8c00"
    return "#43a047"

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div class="yt-pill">▶</div>
    <div>
        <div class="app-title">YouTube Comment Analyser</div>
        <div class="app-subtitle">Identify toxic, borderline, and harmful comments using AI</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── INPUT ─────────────────────────────────────────────────────────────────────
url = st.text_input("", placeholder="Paste a YouTube video URL — e.g. https://www.youtube.com/watch?v=...")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    order = st.selectbox("Sort comments by", ["Top (Relevance)", "Newest"])
with col2:
    max_comments = st.slider("Number of comments", 20, 300, 100, step=10)
with col3:
    st.markdown("<div style='margin-top:1.9rem'></div>", unsafe_allow_html=True)
    run = st.button("Analyse →", type="primary", use_container_width=True)

order_val = "relevance" if "Relevance" in order else "time"

# ── RUN ───────────────────────────────────────────────────────────────────────
if run:
    video_id = extract_video_id(url)
    if not video_id:
        st.error("⚠️ That doesn't look like a valid YouTube URL. Please check and try again.")
        st.stop()

    # Video info → sidebar
    with st.spinner("Fetching video info…"):
        info = fetch_video_info(YOUTUBE_API_KEY, video_id)

    if info:
        with st.sidebar:
            if info["thumbnail"]:
                st.image(info["thumbnail"], use_container_width=True)
            st.markdown(f"""
            <div class="meta-block">
                <div class="meta-item">
                    <div class="meta-key">Video Title</div>
                    <div class="meta-val">{info['title']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-key">Channel</div>
                    <div class="meta-val">{info['channel']}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-key">Upload Date</div>
                    <div class="meta-val">{format_date(info['published'])}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Comments
    with st.spinner("Fetching comments…"):
        comments = fetch_comments(YOUTUBE_API_KEY, video_id, order_val, max_comments)
    if not comments:
        st.warning("No comments found for this video.")
        st.stop()

    # Analysis
    with st.spinner("Scoring comments with AI — this may take a moment…"):
        df = analyse_comments(tuple(comments))

    toxic      = df[df["label"] == "toxic"]
    borderline = df[df["label"] == "borderline"]
    normal     = df[df["label"] == "normal"]

    # ── METRICS ──────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card mc-total">
            <div class="m-label">Total Analysed</div>
            <div class="m-value">{len(df)}</div>
        </div>
        <div class="metric-card mc-toxic">
            <div class="m-label">🔴 Toxic</div>
            <div class="m-value">{len(toxic)}</div>
        </div>
        <div class="metric-card mc-border">
            <div class="m-label">🟠 Borderline</div>
            <div class="m-value">{len(borderline)}</div>
        </div>
        <div class="metric-card mc-normal">
            <div class="m-label">🟢 Normal</div>
            <div class="m-value">{len(normal)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── CHARTS ───────────────────────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-title">📊 Sentiment Breakdown</div>', unsafe_allow_html=True)
        import matplotlib.pyplot as plt

        lbls = ["Normal", "Borderline", "Toxic"]
        cnts = [len(normal), len(borderline), len(toxic)]
        clrs = ["#43a047", "#fb8c00", "#e53935"]

        fig, ax = plt.subplots(figsize=(5, 2.8))
        bars = ax.barh(lbls, cnts, color=clrs, height=0.45, edgecolor="none")
        ax.bar_label(bars, padding=6, fontsize=11, fontweight="bold", color="#1a1a1a")
        ax.set_xlabel("Comments", color="#9b8b8b", fontsize=9)
        for spine in ["top", "right", "left"]:
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color("#f0dada")
        ax.tick_params(colors="#7a5f5f", left=False)
        ax.set_facecolor("#f9f4f4")
        fig.patch.set_facecolor("#f9f4f4")
        ax.set_xlim(0, max(cnts) * 1.28 if max(cnts) > 0 else 1)
        ax.grid(axis="x", color="#f0dada", linewidth=1)
        plt.tight_layout(pad=0.5)
        st.pyplot(fig)
        plt.close(fig)

    with right:
        st.markdown('<div class="section-title">🔬 Toxicity Types — Average Score</div>', unsafe_allow_html=True)
        avg = df[TYPE_COLS].mean()
        for col in TYPE_COLS:
            emoji_label, explanation = TOXICITY_META[col]
            score = avg[col]
            clr   = bar_color(score)
            st.markdown(f"""
            <div class="score-block">
                <div class="score-header">
                    <span class="score-name">{emoji_label}
                        <span class="score-desc">— {explanation}</span>
                    </span>
                    <span class="score-pct" style="color:{clr}">{score:.0%}</span>
                </div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{score*100:.1f}%; background:{clr};"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)

    # ── TOP COMMENTS ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">🚨 Top Comments to Review</div>', unsafe_allow_html=True)
    st.caption("Ranked by toxicity score — prioritise these for moderation")

    if toxic.empty and borderline.empty:
        st.success("✅ No toxic or borderline comments detected!")
    else:
        top = (pd.concat([toxic, borderline])
               .sort_values("toxicity", ascending=False)
               .head(10))

        for _, row in top.iterrows():
            lbl       = row["label"]
            score     = row["toxicity"]
            dom_type  = row[TYPE_COLS].idxmax()
            e_lbl, _  = TOXICITY_META[dom_type]
            card_cls  = "cc-toxic"      if lbl == "toxic" else "cc-borderline"
            badge_cls = "badge-toxic"   if lbl == "toxic" else "badge-borderline"
            badge_txt = "🔴 Toxic"      if lbl == "toxic" else "🟠 Borderline"

            st.markdown(f"""
            <div class="comment-card {card_cls}">
                <span class="badge {badge_cls}">{badge_txt}</span>
                <span class="type-tag">{e_lbl}</span>
                <div class="comment-text">{row['comment']}</div>
                <div class="comment-score">Toxicity score: {score:.0%}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<hr class="soft-divider">', unsafe_allow_html=True)

    # ── ALL COMMENTS TABLE ────────────────────────────────────────────────────
    with st.expander("📋 View all comments with scores"):
        display = (
            df[["comment", "label", "toxicity", "insult", "obscene", "threat", "identity_attack"]]
            .sort_values("toxicity", ascending=False)
            .copy()
        )
        fmt_cols = ["toxicity", "insult", "obscene", "threat", "identity_attack"]
        st.dataframe(
            display.style.format({c: "{:.0%}" for c in fmt_cols}),
            use_container_width=True,
            hide_index=True,
        )
