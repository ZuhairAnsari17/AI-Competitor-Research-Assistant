"""
COMPETITOR INTELLIGENCE PLATFORM v2.0
Production-grade Streamlit dashboard
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

BRAND = {
    "bg":       "#07090D", "surface":  "#0D1117", "surface2": "#111822",
    "border":   "#1C2740", "border2":  "#243050",
    "accent":   "#3B82F6", "accent2":  "#06B6D4",
    "green":    "#10B981", "red":      "#EF4444",
    "amber":    "#F59E0B", "purple":   "#8B5CF6",
    "text":     "#E2EAF4", "muted":    "#4B6180", "muted2": "#6B829A",
}

CHART_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(13,17,23,0.6)",
    font=dict(family="'IBM Plex Mono', monospace", color=BRAND["muted2"], size=11),
    margin=dict(l=4, r=4, t=24, b=4),
    xaxis=dict(gridcolor=BRAND["border"], linecolor=BRAND["border"],
               tickfont=dict(color=BRAND["muted"], size=10)),
    yaxis=dict(gridcolor=BRAND["border"], linecolor=BRAND["border"],
               tickfont=dict(color=BRAND["muted"], size=10)),
)

COMP_COLORS = ["#3B82F6","#06B6D4","#10B981","#8B5CF6","#F59E0B","#EF4444","#EC4899","#14B8A6"]

st.set_page_config(page_title="Competitor Intel", page_icon="◈", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
*, html, body, [class*="css"] {{ font-family: 'Space Grotesk', sans-serif; box-sizing: border-box; }}
.stApp {{ background: {BRAND['bg']}; color: {BRAND['text']}; }}
div[data-testid="stSidebar"] {{ background: {BRAND['surface']} !important; border-right: 1px solid {BRAND['border']} !important; }}
div[data-testid="stSidebar"] * {{ color: {BRAND['text']} !important; }}
div[data-testid="stSidebarContent"] {{ padding: 0 !important; }}
div[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 2px !important; display: flex; flex-direction: column; }}
div[data-testid="stSidebar"] label {{ background: transparent !important; border: none !important; border-radius: 6px !important; padding: 9px 14px !important; font-size: 0.8rem !important; font-weight: 500 !important; cursor: pointer !important; color: {BRAND['muted2']} !important; transition: background 0.15s !important; }}
div[data-testid="stSidebar"] label:hover {{ background: {BRAND['surface2']} !important; color: {BRAND['text']} !important; }}
div[data-testid="stSidebar"] label[data-checked="true"], div[data-testid="stSidebar"] label[aria-checked="true"] {{ background: rgba(59,130,246,0.12) !important; color: {BRAND['accent']} !important; border-left: 2px solid {BRAND['accent']} !important; }}
#MainMenu, footer, header {{ visibility: hidden; }}
div[data-testid="stDecoration"] {{ display: none; }}
.stDeployButton {{ display: none; }}
section[data-testid="stSidebar"] > div:first-child {{ padding-top: 0; }}
div[data-testid="stSelectbox"] > div, div[data-testid="stMultiSelect"] > div {{ background: {BRAND['surface2']} !important; border: 1px solid {BRAND['border']} !important; border-radius: 6px !important; }}
.stButton > button {{ background: {BRAND['accent']} !important; color: #fff !important; font-weight: 600 !important; font-size: 0.8rem !important; border: none !important; border-radius: 6px !important; padding: 8px 18px !important; }}
.stButton > button:hover {{ opacity: 0.85 !important; }}
div[data-testid="stDataFrame"] {{ border: 1px solid {BRAND['border']} !important; border-radius: 8px !important; overflow: hidden; }}
div[data-testid="stDataFrame"] th {{ background: {BRAND['surface2']} !important; color: {BRAND['muted2']} !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.7rem !important; text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 1px solid {BRAND['border']} !important; }}
div[data-testid="stDataFrame"] td {{ background: {BRAND['surface']} !important; color: {BRAND['text']} !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.78rem !important; border-bottom: 1px solid {BRAND['border']} !important; }}
div[data-testid="stMetric"] {{ background: {BRAND['surface']} !important; border: 1px solid {BRAND['border']} !important; border-radius: 10px !important; padding: 14px 18px !important; }}
div[data-testid="stMetricValue"] {{ font-family: 'IBM Plex Mono', monospace !important; color: {BRAND['text']} !important; font-size: 1.6rem !important; }}
div[data-testid="stMetricLabel"] {{ color: {BRAND['muted']} !important; font-size: 0.68rem !important; text-transform: uppercase; letter-spacing: 0.1em; }}
div[data-testid="stMetricDelta"] svg {{ display: none; }}
div[data-testid="stTabs"] button {{ font-family: 'IBM Plex Mono', monospace !important; font-size: 0.72rem !important; color: {BRAND['muted']} !important; text-transform: uppercase; letter-spacing: 0.08em; }}
div[data-testid="stTabs"] button[aria-selected="true"] {{ color: {BRAND['accent']} !important; border-bottom: 2px solid {BRAND['accent']} !important; }}
.page-header {{ padding: 20px 0 16px; border-bottom: 1px solid {BRAND['border']}; margin-bottom: 20px; }}
.page-title {{ font-size: 1.5rem; font-weight: 700; color: {BRAND['text']}; letter-spacing: 0.02em; }}
.page-subtitle {{ font-size: 0.78rem; color: {BRAND['muted2']}; margin-top: 4px; font-family: 'IBM Plex Mono', monospace; }}
.section-label {{ font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: {BRAND['muted']}; margin: 16px 0 8px; padding: 4px 0; border-bottom: 1px solid {BRAND['border']}; }}
.feed-card {{ background: {BRAND['surface']}; border: 1px solid {BRAND['border']}; border-radius: 10px; padding: 16px 18px; margin-bottom: 10px; }}
.feed-card-accent-blue  {{ border-left: 3px solid {BRAND['accent']}; }}
.feed-card-accent-green {{ border-left: 3px solid {BRAND['green']}; }}
.feed-card-accent-amber {{ border-left: 3px solid {BRAND['amber']}; }}
.feed-card-accent-purple {{ border-left: 3px solid {BRAND['purple']}; }}
.feed-card-accent-red {{ border-left: 3px solid {BRAND['red']}; }}
.feed-card-accent-cyan  {{ border-left: 3px solid {BRAND['accent2']}; }}
.card-eyebrow {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
.card-title {{ font-size: 0.92rem; font-weight: 600; color: {BRAND['text']}; margin-bottom: 6px; line-height: 1.4; }}
.card-summary {{ font-size: 0.8rem; color: {BRAND['muted2']}; line-height: 1.5; margin-bottom: 6px; }}
.card-insight {{ font-size: 0.75rem; color: {BRAND['accent']}; line-height: 1.5; margin-bottom: 4px; }}
.card-meta {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; color: {BRAND['muted']}; display: flex; align-items: center; gap: 12px; margin-top: 8px; flex-wrap: wrap; }}
.tag {{ display: inline-block; background: {BRAND['surface2']}; border: 1px solid {BRAND['border']}; color: {BRAND['muted2']}; font-size: 0.62rem; padding: 2px 7px; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; }}
.tag-comp {{ background: rgba(59,130,246,0.1); color: {BRAND['accent']}; border-color: rgba(59,130,246,0.2); }}
.tag-high {{ background: rgba(239,68,68,0.1); color: {BRAND['red']}; border-color: rgba(239,68,68,0.2); }}
.tag-medium {{ background: rgba(245,158,11,0.1); color: {BRAND['amber']}; border-color: rgba(245,158,11,0.2); }}
.tag-low {{ background: rgba(16,185,129,0.1); color: {BRAND['green']}; border-color: rgba(16,185,129,0.2); }}
.trend-bar {{ height: 4px; background: {BRAND['border']}; border-radius: 2px; margin-top: 6px; }}
.trend-fill {{ height: 4px; border-radius: 2px; }}
.kpi-block {{ background: {BRAND['surface']}; border: 1px solid {BRAND['border']}; border-radius: 10px; padding: 16px 18px; }}
.kpi-val {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.8rem; font-weight: 700; color: {BRAND['text']}; }}
.kpi-label {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em; color: {BRAND['muted']}; margin-top: 4px; }}
.sidebar-section {{ font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: {BRAND['muted']}; padding: 14px 14px 6px; }}
.sidebar-divider {{ border: none; border-top: 1px solid {BRAND['border']}; margin: 8px 0; }}
.alert-banner {{ background: rgba(245,158,11,0.05); border: 1px solid rgba(245,158,11,0.2); border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }}
.alert-title {{ font-size: 0.78rem; font-weight: 600; color: {BRAND['amber']}; margin-bottom: 4px; }}
.empty-state {{ text-align: center; padding: 60px 20px; color: {BRAND['muted']}; }}
.empty-state .icon {{ font-size: 2.5rem; margin-bottom: 12px; }}
.progress-bar {{ background: {BRAND['border']}; border-radius: 3px; height: 6px; overflow: hidden; }}
.progress-fill {{ height: 6px; border-radius: 3px; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────

def api(endpoint, params=None):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def api_post(endpoint):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fdate(s):
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)
        now   = datetime.utcnow()
        delta = (now.date() - dt.date()).days
        if delta == 0:
            return f"Today {dt.strftime('%H:%M')} UTC"
        if delta == 1:
            return f"Yesterday {dt.strftime('%H:%M')} UTC"
        return dt.strftime("%b %d %Y")
    except Exception:
        return str(s)[:10]

def fnum(n):
    if n is None:
        return "—"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def _trend_color(score: float) -> str:
    if score >= 0.7:
        return BRAND["red"]
    if score >= 0.4:
        return BRAND["amber"]
    return BRAND["green"]

def comp_color(name: str, names: list) -> str:
    try:
        return COMP_COLORS[names.index(name) % len(COMP_COLORS)]
    except Exception:
        return COMP_COLORS[0]

def plotly_cfg():
    return {"displayModeBar": False}

# ── Card builder helpers (pre-compute HTML — avoids ternary-in-fstring rendering bugs) ──

def _tag(label, extra_class=""):
    return f'<span class="tag {extra_class}">{label}</span>'

def _trend_bar_html(score: float, color: str) -> str:
    pct = int((score or 0) * 100)
    return f'<div class="trend-bar"><div class="trend-fill" style="width:{pct}%;background:{color}"></div></div>'

def _importance_tag(imp: str) -> str:
    icons = {"high": "🔴", "medium": "🟠", "low": "🟢"}
    icon = icons.get(imp, "")
    cls  = f"tag-{imp}" if imp in icons else "tag"
    return f'<span class="tag {cls}">{icon} {imp.upper()}</span>'

def _mono_span(text: str, color: str, size: str = "0.62rem") -> str:
    """Safe mono span — no nested quotes inside style attr."""
    return f'<span style="font-family:monospace;font-size:{size};color:{color}">{text}</span>'

def _blog_card(post: dict) -> str:
    ts   = float(post.get("trend_score") or 0.0)
    imp  = post.get("importance") or "medium"
    tc   = _trend_color(ts)
    comp = post.get("competitor", "")
    url  = post.get("url", "#")
    title   = post.get("title", "")
    summary = post.get("summary", "")
    key_ins = post.get("key_insights", "")
    why_itm = post.get("why_it_matters", "")
    kws     = post.get("keywords") or []
    date    = fdate(post.get("published_at") or post.get("detected_at"))
    source  = post.get("source", "rss")

    kw_html      = " ".join(_tag(k) for k in kws[:5])
    insight_html = f'<div class="card-insight">&#128161; {key_ins}</div>' if key_ins else ""
    why_html     = f'<div style="font-size:0.75rem;color:{BRAND["muted2"]};margin-top:4px">&#127919; {why_itm}</div>' if why_itm else ""
    summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""
    trend_span   = _mono_span(f"&#9650; {ts:.2f}", tc)
    via_span     = _mono_span("via " + source, BRAND["muted"])
    imp_tag      = _importance_tag(imp)
    comp_tag     = _tag(comp, "tag-comp")
    trend_bar    = _trend_bar_html(ts, tc)
    title_color  = BRAND["text"]

    return (
        '<div class="feed-card feed-card-accent-blue">' +
        '<div class="card-eyebrow">' + comp_tag + imp_tag + trend_span + '</div>' +
        f'<div class="card-title"><a href="{url}" target="_blank" style="color:{title_color};text-decoration:none">{title}</a></div>' +
        summary_html + insight_html + why_html + trend_bar +
        '<div class="card-meta">' + kw_html + f'<span>{date}</span>' + via_span + '</div>' +
        '</div>'
    )

def _video_card(v: dict) -> str:
    ts   = float(v.get("trend_score") or 0.0)
    tc   = _trend_color(ts)
    comp = v.get("competitor", "")
    url  = v.get("url", "#")
    title   = v.get("title", "")
    summary = v.get("summary", "")
    cat     = v.get("category", "")
    views   = fnum(v.get("views", 0))
    likes   = fnum(v.get("likes", 0))
    comments = fnum(v.get("comments", 0))
    date    = fdate(v.get("published_at") or v.get("detected_at"))

    cat_html      = _tag(cat) if cat else ""
    summary_html  = f'<div class="card-summary">{summary}</div>' if summary else ""
    trend_span    = _mono_span(f"&#9650; {ts:.2f}", tc)
    trend_bar     = _trend_bar_html(ts, tc)
    comp_tag      = _tag(comp, "tag-comp")
    title_color   = BRAND["text"]

    return (
        '<div class="feed-card feed-card-accent-red">' +
        '<div class="card-eyebrow">' + comp_tag + cat_html + trend_span + '</div>' +
        f'<div class="card-title"><a href="{url}" target="_blank" style="color:{title_color};text-decoration:none">{title}</a></div>' +
        summary_html + trend_bar +
        f'<div class="card-meta"><span>&#128065; {views}</span><span>&#128077; {likes}</span><span>&#128172; {comments}</span><span>{date}</span></div>' +
        '</div>'
    )

def _reddit_card(m: dict) -> str:
    ts   = float(m.get("trend_score") or 0.0)
    tc   = _trend_color(ts)
    sl   = m.get("sentiment_label", "neutral")
    comp = m.get("competitor", "")
    url  = m.get("url", "#")
    title   = m.get("title", "")
    summary = m.get("summary", "")
    topic   = m.get("topic", "")
    sub     = m.get("subreddit", "")
    date    = fdate(m.get("created_at") or m.get("detected_at"))

    sent_color   = BRAND["green"] if sl=="positive" else BRAND["red"] if sl=="negative" else BRAND["muted"]
    sent_icon    = "&#9989;" if sl=="positive" else "&#10060;" if sl=="negative" else "&#10135;"
    topic_html   = _tag(topic) if topic else ""
    summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""
    sent_span    = _mono_span(sent_icon + " " + sl, sent_color)
    trend_span   = _mono_span(f"&#9650; {ts:.2f}", tc)
    comp_tag     = _tag(comp, "tag-comp")
    trend_bar    = _trend_bar_html(ts, tc)
    title_color  = BRAND["text"]

    return (
        '<div class="feed-card feed-card-accent-purple">' +
        '<div class="card-eyebrow">' + comp_tag + sent_span + topic_html + trend_span + '</div>' +
        f'<div class="card-title"><a href="{url}" target="_blank" style="color:{title_color};text-decoration:none">{title}</a></div>' +
        summary_html + trend_bar +
        f'<div class="card-meta"><span>r/{sub}</span><span>{date}</span></div>' +
        '</div>'
    )

def _ad_card(ad: dict) -> str:
    comp      = ad.get("competitor", "")
    url       = ad.get("landing_url") or "#"
    headline  = ad.get("headline") or ad.get("page_name") or comp
    ad_summ   = ad.get("ad_summary", "")
    ad_type   = ad.get("ad_type", "")
    cta_text  = ad.get("cta", "")
    desc      = ad.get("description", "")
    raw_body  = ad.get("ad_creative_body", "")
    plats     = ad.get("platforms") or ["facebook"]
    plat_str  = " · ".join(plats) if isinstance(plats, list) else str(plats)
    date      = fdate(ad.get("delivery_start_time") or ad.get("detected_at"))
    ad_id     = str(ad.get("ad_id", "—"))[:14]
    source    = ad.get("source", "")

    display_body = desc or raw_body[:300] or ad_summ or ""
    has_body     = bool(display_body)
    body_color   = BRAND["muted2"] if has_body else BRAND["muted"]
    body_style   = "font-style:italic" if not has_body else ""
    body_text    = display_body if has_body else "No creative text — set META_ACCESS_TOKEN for full ad copy"

    type_html  = _mono_span(ad_type, BRAND["amber"]) if ad_type else ""
    cta_html   = _mono_span("CTA: " + cta_text, BRAND["green"]) if cta_text else ""
    summ_html  = f'<div class="card-summary">{ad_summ}</div>' if ad_summ else ""
    ad_span    = _mono_span("AD", BRAND["purple"])
    plat_span  = _mono_span("&#128241; " + plat_str, BRAND["muted"])
    id_span    = _mono_span("ID: " + ad_id, BRAND["muted"])
    via_span   = _mono_span("via " + source, BRAND["muted"]) if source else ""
    comp_tag   = _tag(comp, "tag-comp")
    bg2        = BRAND["surface2"]
    brd        = BRAND["border"]

    body_div = f'<div style="font-family:monospace;font-size:0.75rem;background:{bg2};border:1px solid {brd};border-radius:6px;padding:10px 12px;color:{body_color};{body_style}">{body_text}</div>'

    return (
        '<div class="feed-card feed-card-accent-purple">' +
        '<div class="card-eyebrow">' + comp_tag + ad_span + plat_span + type_html + cta_html + '</div>' +
        f'<div class="card-title">{headline}</div>' +
        summ_html + body_div +
        f'<div class="card-meta"><span>Started {date}</span>' + id_span + via_span + '</div>' +
        '</div>'
    )

def _serp_card(r: dict, type_colors: dict, type_icons: dict) -> str:
    ts     = float(r.get("trend_score") or 0.0)
    tc     = _trend_color(ts)
    imp    = r.get("importance", "medium")
    rtype  = r.get("result_type", "")
    comp   = r.get("competitor", "")
    url    = r.get("url", "#")
    title  = r.get("title", "")
    summary    = r.get("summary", "") or r.get("snippet", "")
    key_ins    = r.get("key_insights", "")
    why_itm    = r.get("why_it_matters", "")
    source     = r.get("source", "")
    date       = fdate(r.get("published_at") or r.get("detected_at"))
    acc        = type_colors.get(rtype, BRAND["accent2"])
    icon       = type_icons.get(rtype, "&#128269;")

    summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""
    insight_html = f'<div class="card-insight">&#128161; {key_ins}</div>' if key_ins else ""
    why_html     = f'<div style="font-size:0.75rem;color:{BRAND["muted2"]};margin-top:4px">&#127919; {why_itm}</div>' if why_itm else ""

    type_span   = _mono_span(icon + " " + rtype, acc)
    trend_span  = _mono_span(f"&#9650; {ts:.2f}", tc)
    imp_tag     = _importance_tag(imp)
    comp_tag    = _tag(comp, "tag-comp")
    trend_bar   = _trend_bar_html(ts, tc)
    title_color = BRAND["text"]

    return (
        f'<div class="feed-card" style="border-left:3px solid {acc}">' +
        '<div class="card-eyebrow">' + comp_tag + type_span + imp_tag + trend_span + '</div>' +
        f'<div class="card-title"><a href="{url}" target="_blank" style="color:{title_color};text-decoration:none">{title}</a></div>' +
        summary_html + insight_html + why_html + trend_bar +
        f'<div class="card-meta"><span>{source}</span><span>{date}</span></div>' +
        '</div>'
    )


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
<div style="padding:20px 14px 12px;border-bottom:1px solid {BRAND['border']}">
  <div style="font-size:1.1rem;font-weight:700;color:{BRAND['text']};letter-spacing:0.03em">&#9672; Competitor Intel</div>
  <div style="font-size:0.65rem;color:{BRAND['muted']};font-family:monospace;margin-top:3px">v2.0 · AI-Powered</div>
</div>
""", unsafe_allow_html=True)

    # Robust API health check
    api_ok = False
    try:
        r = requests.get(f"{API_BASE}/health", timeout=4)
        api_ok = r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        api_ok = False

    if api_ok:
        st.markdown(f'<div style="padding:8px 14px;font-size:0.7rem;color:{BRAND["green"]}">&#9679; API connected — {API_BASE}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div style="padding:10px 14px;font-size:0.68rem;color:{BRAND['red']};background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);border-radius:6px;margin:8px 12px">
&#10007; API offline — start with:<br>
<code style="font-size:0.62rem">uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload</code><br>
<span style="color:{BRAND['muted']}">Connecting to: {API_BASE}</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Navigation</div>', unsafe_allow_html=True)
    page = st.radio(
        label="", label_visibility="collapsed",
        options=[
            "Overview",
            "Blog Intelligence",
            "YouTube Tracker",
            "Reddit Monitor",
            "Meta Ads",
            "SerpAPI Intelligence",
            "Trending Topics",
            "Competitive Matrix",
            "Agent Health",
            "MLflow Analytics",
        ],
    )

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section">Filter</div>', unsafe_allow_html=True)
    comps_raw   = api("/api/competitors") or []
    comp_names  = [c["name"] for c in comps_raw]
    comp_filter = st.selectbox("Competitor", ["All"] + comp_names, label_visibility="collapsed")
    if comp_filter == "All":
        comp_filter = None

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
    if st.button("&#8635; Poll Now", use_container_width=True):
        api_post("/api/trigger-poll")
        st.success("Poll triggered")
    if st.button("&#8634; Reload Config", use_container_width=True):
        api_post("/api/reload-config")
        st.success("Config reloaded")

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
    summ_side = api("/api/summary") or {}
    st.markdown(f"""
<div style="padding:10px 14px">
  <div style="font-size:0.62rem;color:{BRAND['muted']};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px">Last Poll</div>
  <div style="font-family:monospace;font-size:0.72rem;color:{BRAND['text']}">{fdate(summ_side.get('last_poll'))}</div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#9672; Overview</div>
  <div class="page-subtitle">Intelligence summary · recent posts · trending competitors · platform activity</div>
</div>""", unsafe_allow_html=True)

    summ = api("/api/summary") or {}

    # ── KPI row ──────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Competitors",  summ.get("competitors_tracked", 0))
    k2.metric("Blog Posts 7d", summ.get("blog_posts_7d", 0))
    k3.metric("Videos 7d",    summ.get("youtube_videos_7d", 0))
    k4.metric("Reddit 7d",    summ.get("reddit_mentions_7d", 0))
    k5.metric("Ads 7d",       summ.get("ads_detected_7d", 0))
    k6.metric("SERP 7d",      summ.get("serp_results_7d", 0))

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Trending competitor + most active platform ────────────────────
    t1, t2 = st.columns(2)
    with t1:
        trending_comp = summ.get("trending_competitor") or "—"
        st.markdown(f"""
<div class="kpi-block">
  <div class="kpi-label">&#128293; Trending Competitor</div>
  <div class="kpi-val" style="color:{BRAND['accent']};font-size:1.4rem;margin-top:6px">{trending_comp}</div>
  <div style="font-size:0.72rem;color:{BRAND['muted']};margin-top:4px">Most activity in last 7 days</div>
</div>""", unsafe_allow_html=True)
    with t2:
        active_platform = summ.get("most_active_platform") or "—"
        st.markdown(f"""
<div class="kpi-block">
  <div class="kpi-label">&#128225; Most Active Platform</div>
  <div class="kpi-val" style="color:{BRAND['accent2']};font-size:1.4rem;margin-top:6px">{active_platform}</div>
  <div style="font-size:0.72rem;color:{BRAND['muted']};margin-top:4px">Highest signal volume this week</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Platform activity bar chart ───────────────────────────────────
    st.markdown('<div class="section-label">&#9702; Posts by Platform (7 days)</div>', unsafe_allow_html=True)
    pc = summ.get("platform_counts", {})
    if pc:
        fig = go.Figure(go.Bar(
            x=list(pc.keys()), y=list(pc.values()),
            marker_color=[BRAND["accent"], BRAND["red"], BRAND["purple"],
                         BRAND["amber"], BRAND["accent2"]],
            marker_line_width=0,
            text=list(pc.values()), textposition="outside",
            textfont=dict(color=BRAND["muted2"], size=11),
        ))
        fig.update_layout(height=220, showlegend=False, **CHART_BASE)
        st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    # ── Trending items ────────────────────────────────────────────────
    st.markdown('<div class="section-label">&#128293; Trending Now (High Signal Items)</div>', unsafe_allow_html=True)
    trending_items = api("/api/stats/trending", {"limit": 8}) or []
    if not trending_items:
        st.markdown('<div class="empty-state"><div class="icon">&#128293;</div>No high-signal items yet · run a poll</div>', unsafe_allow_html=True)
    else:
        plat_acc = {"Blog": BRAND["accent"], "YouTube": BRAND["red"],
                    "Reddit": BRAND["purple"], "SerpAPI": BRAND["accent2"], "Meta Ads": BRAND["amber"]}
        for item in trending_items:
            ts  = float(item.get("trend_score") or 0.0)
            tc  = _trend_color(ts)
            imp = item.get("importance", "medium")
            acc = plat_acc.get(item.get("platform", ""), BRAND["accent"])
            plat = item.get("platform", "")
            comp = item.get("competitor", "")
            url  = item.get("url", "#")
            title   = item.get("title", "")
            summary = item.get("summary", "")
            date    = fdate(item.get("detected_at"))
            summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""
            plat_span  = _mono_span("&#128225; " + plat, acc)
            score_span = _mono_span(f"&#9650; {ts:.2f}", BRAND["amber"])
            imp_tag    = _importance_tag(imp)
            comp_tag   = _tag(comp, "tag-comp")
            trend_bar  = _trend_bar_html(ts, acc)
            title_c    = BRAND["text"]
            card_html  = (
                f'<div class="feed-card" style="border-left:3px solid {acc}">' +
                '<div class="card-eyebrow">' + comp_tag + plat_span + imp_tag + score_span + '</div>' +
                f'<div class="card-title"><a href="{url}" target="_blank" style="color:{title_c};text-decoration:none">{title}</a></div>' +
                summary_html + trend_bar +
                f'<div class="card-meta"><span>{date}</span></div>' +
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    # ── Recent Blog Posts ─────────────────────────────────────────────
    st.markdown('<div class="section-label">&#128240; Recent Blog Posts</div>', unsafe_allow_html=True)
    recent_posts = api("/api/blog-posts", {"limit": 5, **({"competitor": comp_filter} if comp_filter else {})}) or []
    if not recent_posts:
        st.markdown(f'<div style="color:{BRAND["muted"]};font-size:0.8rem;padding:12px 0">No blog posts yet · run a poll</div>', unsafe_allow_html=True)
    else:
        for post in recent_posts:
            st.markdown(_blog_card(post), unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;padding:8px 0"><a href="#" style="color:{BRAND["muted2"]};font-size:0.72rem;font-family:monospace">&#8594; View all in Blog Intelligence tab</a></div>', unsafe_allow_html=True)

    # ── Recent YouTube Videos ─────────────────────────────────────────
    st.markdown('<div class="section-label">&#9654; Recent YouTube Videos</div>', unsafe_allow_html=True)
    recent_vids = api("/api/youtube", {"limit": 5, **({"competitor": comp_filter} if comp_filter else {})}) or []
    if not recent_vids:
        st.markdown(f'<div style="color:{BRAND["muted"]};font-size:0.8rem;padding:12px 0">No videos yet · set youtube_channel_id in config.yaml</div>', unsafe_allow_html=True)
    else:
        for v in recent_vids:
            st.markdown(_video_card(v), unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;padding:8px 0"><a href="#" style="color:{BRAND["muted2"]};font-size:0.72rem;font-family:monospace">&#8594; View all in YouTube Tracker tab</a></div>', unsafe_allow_html=True)

    # ── Competitor activity chart ──────────────────────────────────────
    st.markdown('<div class="section-label">&#9702; Competitor Activity Breakdown</div>', unsafe_allow_html=True)
    all_posts = pd.DataFrame(api("/api/blog-posts", {"limit": 500}) or [])
    all_vids  = pd.DataFrame(api("/api/youtube",    {"limit": 500}) or [])
    all_red   = pd.DataFrame(api("/api/reddit",     {"limit": 500}) or [])

    if comp_names:
        fig2 = go.Figure()
        for comp in comp_names:
            color = comp_color(comp, comp_names)
            vals = [
                len(all_posts[all_posts["competitor"]==comp]) if not all_posts.empty and "competitor" in all_posts.columns else 0,
                len(all_vids[all_vids["competitor"]==comp])   if not all_vids.empty  and "competitor" in all_vids.columns  else 0,
                len(all_red[all_red["competitor"]==comp])     if not all_red.empty   and "competitor" in all_red.columns   else 0,
            ]
            fig2.add_trace(go.Bar(name=comp, x=["Blog","YouTube","Reddit"], y=vals,
                                  marker_color=color, marker_line_width=0))
        fig2.update_layout(barmode="group", height=240, showlegend=True,
                           legend=dict(font=dict(color=BRAND["muted"],size=10),bgcolor="rgba(0,0,0,0)"),
                           **CHART_BASE)
        st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: BLOG INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Blog Intelligence":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#128240; Blog Intelligence</div>
  <div class="page-subtitle">RSS feeds · LLM summaries · competitive signals · trend scoring</div>
</div>""", unsafe_allow_html=True)

    params = {"limit": 200, **({"competitor": comp_filter} if comp_filter else {})}
    posts  = api("/api/blog-posts", params) or []

    if not posts:
        st.markdown('<div class="empty-state"><div class="icon">&#128240;</div>No blog posts yet · run a poll</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(posts)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Posts",   len(posts))
    m2.metric("Competitors",   df["competitor"].nunique() if "competitor" in df.columns else 0)
    m3.metric("&#128308; High Priority", sum(1 for p in posts if p.get("importance")=="high"))
    avg_t = round(pd.to_numeric(df.get("trend_score", pd.Series([0])), errors="coerce").mean(), 2)
    m4.metric("Avg Trend Score", f"{avg_t:.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown('<div class="section-label">&#9702; Posts by Competitor</div>', unsafe_allow_html=True)
        if "competitor" in df.columns:
            ac = df["competitor"].value_counts().reset_index()
            ac.columns = ["Competitor","Posts"]
            fig = go.Figure(go.Bar(x=ac["Competitor"], y=ac["Posts"],
                                   marker_color=[comp_color(c, comp_names) for c in ac["Competitor"]],
                                   marker_line_width=0))
            fig.update_layout(height=200, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    with ch2:
        st.markdown('<div class="section-label">&#9702; Avg Trend Score by Competitor</div>', unsafe_allow_html=True)
        if "trend_score" in df.columns and "competitor" in df.columns:
            ts_df = df.groupby("competitor")["trend_score"].mean().reset_index()
            ts_df.columns = ["Competitor","Avg Trend"]
            fig2 = go.Figure(go.Bar(x=ts_df["Competitor"], y=ts_df["Avg Trend"],
                                    marker_color=[comp_color(c, comp_names) for c in ts_df["Competitor"]],
                                    marker_line_width=0))
            fig2.update_layout(height=200, showlegend=False, **{
                **CHART_BASE,
                "yaxis": {**CHART_BASE["yaxis"], "range": [0, 1]},
            })
            st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())

    st.markdown('<div class="section-label">&#9702; Blog Posts</div>', unsafe_allow_html=True)
    s1, s2 = st.columns([2,2])
    with s1:
        sort_b = st.selectbox("Sort", ["Newest","Highest Trend","High Priority"],
                               label_visibility="collapsed", key="blog_sort")
    with s2:
        filter_imp = st.selectbox("Filter", ["All","High","Medium","Low"],
                                   label_visibility="collapsed", key="blog_filter")

    posts_s = posts.copy()
    if filter_imp != "All":
        posts_s = [p for p in posts_s if (p.get("importance") or "").lower() == filter_imp.lower()]
    if sort_b == "Highest Trend":
        posts_s = sorted(posts_s, key=lambda x: x.get("trend_score") or 0, reverse=True)
    elif sort_b == "High Priority":
        posts_s = sorted(posts_s, key=lambda x: 0 if x.get("importance")=="high" else 1)

    for post in posts_s[:40]:
        st.markdown(_blog_card(post), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: YOUTUBE TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "YouTube Tracker":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#9654; YouTube Tracker</div>
  <div class="page-subtitle">Video intelligence · view trends · category breakdown</div>
</div>""", unsafe_allow_html=True)

    params = {"limit": 200, **({"competitor": comp_filter} if comp_filter else {})}
    videos = api("/api/youtube", params) or []

    if not videos:
        st.markdown('<div class="empty-state"><div class="icon">&#9654;</div>No videos yet · set youtube_channel_id in config.yaml</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(videos)
    total_views = int(pd.to_numeric(df.get("views", pd.Series([0])), errors="coerce").sum())
    avg_t = round(pd.to_numeric(df.get("trend_score", pd.Series([0])), errors="coerce").mean(), 2)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Videos",  len(videos))
    m2.metric("Competitors",   df["competitor"].nunique() if "competitor" in df.columns else 0)
    m3.metric("Total Views",   fnum(total_views))
    m4.metric("Avg Trend Score", f"{avg_t:.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown('<div class="section-label">&#9702; Views by Competitor</div>', unsafe_allow_html=True)
        if "competitor" in df.columns and "views" in df.columns:
            vbc = df.groupby("competitor")["views"].sum().reset_index()
            fig = go.Figure(go.Bar(x=vbc["competitor"], y=vbc["views"],
                                   marker_color=[comp_color(c, comp_names) for c in vbc["competitor"]],
                                   marker_line_width=0))
            fig.update_layout(height=200, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    with ch2:
        st.markdown('<div class="section-label">&#9702; Videos by Category</div>', unsafe_allow_html=True)
        if "category" in df.columns:
            cats = df["category"].fillna("other").replace("","other").value_counts()
            if not cats.empty:
                fig2 = go.Figure(go.Pie(
                    labels=cats.index.tolist(), values=cats.values.tolist(),
                    hole=0.55, marker=dict(colors=COMP_COLORS),
                    textfont=dict(color=BRAND["muted2"], size=10),
                ))
                fig2.update_layout(height=200, showlegend=True,
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   legend=dict(font=dict(color=BRAND["muted"],size=9),bgcolor="rgba(0,0,0,0)"),
                                   margin=dict(l=4,r=4,t=4,b=4))
                st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())

    st.markdown('<div class="section-label">&#9702; Videos</div>', unsafe_allow_html=True)
    sort_v = st.selectbox("Sort", ["Newest","Most Views","Highest Trend"],
                           label_visibility="collapsed", key="yt_sort")
    if sort_v == "Most Views":
        vids_s = sorted(videos, key=lambda x: x.get("views") or 0, reverse=True)
    elif sort_v == "Highest Trend":
        vids_s = sorted(videos, key=lambda x: x.get("trend_score") or 0, reverse=True)
    else:
        vids_s = videos

    for v in vids_s[:40]:
        st.markdown(_video_card(v), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REDDIT MONITOR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Reddit Monitor":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#128308; Reddit Monitor</div>
  <div class="page-subtitle">Community mentions · sentiment · topic classification</div>
</div>""", unsafe_allow_html=True)

    params   = {"limit": 200, **({"competitor": comp_filter} if comp_filter else {})}
    mentions = api("/api/reddit", params) or []

    if not mentions:
        st.markdown('<div class="empty-state"><div class="icon">&#128308;</div>No Reddit mentions yet · run a poll</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(mentions)
    pos = sum(1 for m in mentions if m.get("sentiment_label")=="positive")
    neg = sum(1 for m in mentions if m.get("sentiment_label")=="negative")
    avg_sent = round(pd.to_numeric(df.get("sentiment_score", pd.Series([0])), errors="coerce").mean(), 3)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Mentions", len(mentions))
    m2.metric("&#9989; Positive", pos)
    m3.metric("&#10060; Negative", neg)
    m4.metric("Avg Sentiment", f"{avg_sent:+.3f}")

    st.markdown("<br>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown('<div class="section-label">&#9702; Sentiment Distribution</div>', unsafe_allow_html=True)
        if "sentiment_label" in df.columns:
            sc = df["sentiment_label"].value_counts()
            clrs = [BRAND["green"] if l=="positive" else BRAND["red"] if l=="negative" else BRAND["muted"] for l in sc.index]
            fig = go.Figure(go.Bar(x=sc.index.tolist(), y=sc.values.tolist(),
                                   marker_color=clrs, marker_line_width=0))
            fig.update_layout(height=200, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    with ch2:
        st.markdown('<div class="section-label">&#9702; Topic Breakdown</div>', unsafe_allow_html=True)
        if "topic" in df.columns:
            tc_ = df["topic"].fillna("other").value_counts()
            fig2 = go.Figure(go.Bar(x=tc_.index.tolist(), y=tc_.values.tolist(),
                                    marker_color=BRAND["purple"], marker_line_width=0))
            fig2.update_layout(height=200, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())

    st.markdown('<div class="section-label">&#9702; Mentions</div>', unsafe_allow_html=True)
    filt_sent = st.selectbox("Sentiment", ["All","positive","neutral","negative"],
                              label_visibility="collapsed", key="reddit_filt")
    ments_s = mentions if filt_sent=="All" else [m for m in mentions if m.get("sentiment_label")==filt_sent]

    for m in ments_s[:40]:
        st.markdown(_reddit_card(m), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: META ADS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Meta Ads":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#128226; Meta Ads Intelligence</div>
  <div class="page-subtitle">Facebook Ad Library · creative analysis · platform breakdown</div>
</div>""", unsafe_allow_html=True)

    st.markdown("""
<div class="alert-banner">
  <div class="alert-title">&#8505; For full creative text</div>
  Set <code>META_ACCESS_TOKEN</code> in <code>.env</code> — the official API returns complete ad copy.
  Without it, the GraphQL/HTML scraper is used and may return partial text.
</div>""", unsafe_allow_html=True)

    params = {"limit": 200, **({"competitor": comp_filter} if comp_filter else {})}
    ads    = api("/api/ads", params) or []

    if not ads:
        st.markdown('<div class="empty-state"><div class="icon">&#128226;</div>No ads detected · set META_ACCESS_TOKEN and poll</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(ads)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Ads", len(ads))
    m2.metric("Competitors w/ Ads", df["competitor"].nunique() if "competitor" in df.columns else 0)
    m3.metric("Latest Detected", fdate(df["detected_at"].max()) if "detected_at" in df.columns else "—")

    st.markdown("<br>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown('<div class="section-label">&#9702; Ads per Competitor</div>', unsafe_allow_html=True)
        if "competitor" in df.columns:
            ac = df["competitor"].value_counts().reset_index()
            ac.columns = ["Competitor","Ads"]
            fig = go.Figure(go.Bar(x=ac["Competitor"], y=ac["Ads"],
                                   marker_color=[comp_color(c, comp_names) for c in ac["Competitor"]],
                                   marker_line_width=0))
            fig.update_layout(height=220, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    with ch2:
        st.markdown('<div class="section-label">&#9702; Ads by Type</div>', unsafe_allow_html=True)
        if "ad_type" in df.columns:
            at = df["ad_type"].fillna("unknown").replace("","unknown").value_counts()
            fig2 = go.Figure(go.Bar(x=at.index.tolist(), y=at.values.tolist(),
                                    marker_color=BRAND["purple"], marker_line_width=0))
            fig2.update_layout(height=220, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())

    st.markdown('<div class="section-label">&#9702; Ad Creatives</div>', unsafe_allow_html=True)
    sort_a = st.selectbox("Sort", ["Newest","By Competitor","By Type"],
                           label_visibility="collapsed", key="ads_sort")
    if sort_a == "By Competitor":
        ads_s = sorted(ads, key=lambda x: x.get("competitor",""))
    elif sort_a == "By Type":
        ads_s = sorted(ads, key=lambda x: x.get("ad_type",""))
    else:
        ads_s = ads

    for ad in ads_s[:50]:
        st.markdown(_ad_card(ad), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SERPAPI INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "SerpAPI Intelligence":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#128269; SerpAPI Intelligence</div>
  <div class="page-subtitle">Google news · organic · ads · trending — AI-enriched signals</div>
</div>""", unsafe_allow_html=True)

    params  = {"limit": 200, **({"competitor": comp_filter} if comp_filter else {})}
    results = api("/api/serp", params) or []

    if not results:
        st.markdown("""
<div class="alert-banner">
  <div class="alert-title">&#8505; Enable SerpAPI to collect results</div>
  Add <code>SERPAPI_KEY=your_key</code> to <code>.env</code> and set
  <code>serpapi.enabled: true</code> in <code>config.yaml</code>.
  Free tier: 100 searches/month at <a href="https://serpapi.com" target="_blank" style="color:#3B82F6">serpapi.com</a>
</div>""", unsafe_allow_html=True)
        st.markdown('<div class="empty-state"><div class="icon">&#128269;</div>No SERP results yet · enable SerpAPI and run a poll</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(results)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Results",   len(results))
    m2.metric("Result Types",    df["result_type"].nunique() if "result_type" in df.columns else 0)
    m3.metric("&#128308; High Priority", sum(1 for r in results if r.get("importance")=="high"))
    avg_ts = round(pd.to_numeric(df.get("trend_score", pd.Series([0])), errors="coerce").mean(), 2)
    m4.metric("Avg Trend Score", f"{avg_ts:.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown('<div class="section-label">&#9702; Results by Type</div>', unsafe_allow_html=True)
        if "result_type" in df.columns:
            rt = df["result_type"].value_counts()
            fig = go.Figure(go.Bar(x=rt.index.tolist(), y=rt.values.tolist(),
                                   marker_color=BRAND["accent2"], marker_line_width=0))
            fig.update_layout(height=200, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    with ch2:
        st.markdown('<div class="section-label">&#9702; Trend Score Distribution</div>', unsafe_allow_html=True)
        if "trend_score" in df.columns:
            h_ = (df["trend_score"] >= 0.7).sum()
            m_ = ((df["trend_score"] >= 0.4) & (df["trend_score"] < 0.7)).sum()
            l_ = (df["trend_score"] < 0.4).sum()
            fig2 = go.Figure(go.Bar(
                x=["High (>=0.7)","Medium (0.4-0.7)","Low (<0.4)"],
                y=[h_, m_, l_],
                marker_color=[BRAND["red"], BRAND["amber"], BRAND["green"]],
                marker_line_width=0,
            ))
            fig2.update_layout(height=200, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())

    st.markdown('<div class="section-label">&#9702; SERP Results</div>', unsafe_allow_html=True)
    s1, s2 = st.columns([2,2])
    with s1:
        sort_s = st.selectbox("Sort", ["Newest","Highest Trend","High Priority"],
                               label_visibility="collapsed", key="serp_sort")
    with s2:
        filt_t = st.selectbox("Type", ["All","news","organic","google_ads","trending"],
                               label_visibility="collapsed", key="serp_type")

    TYPE_COLORS = {"news": BRAND["accent"], "organic": BRAND["accent2"],
                   "google_ads": BRAND["amber"], "trending": BRAND["purple"]}
    TYPE_ICONS  = {"news": "&#128240;", "organic": "&#128269;",
                   "google_ads": "&#128176;", "trending": "&#128293;"}

    res_s = results if filt_t=="All" else [r for r in results if r.get("result_type")==filt_t]
    if sort_s == "Highest Trend":
        res_s = sorted(res_s, key=lambda x: x.get("trend_score") or 0, reverse=True)
    elif sort_s == "High Priority":
        res_s = sorted(res_s, key=lambda x: 0 if x.get("importance")=="high" else 1)

    for r in res_s[:40]:
        st.markdown(_serp_card(r, TYPE_COLORS, TYPE_ICONS), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TRENDING TOPICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trending Topics":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#128293; Trending Topics</div>
  <div class="page-subtitle">Cross-platform trend signals · high-importance items</div>
</div>""", unsafe_allow_html=True)

    trending  = api("/api/stats/trending", {"limit": 30}) or []
    top_posts = api("/api/stats/top-posts", {"limit": 6}) or []
    top_vids  = api("/api/stats/top-videos", {"limit": 6}) or []

    if not trending:
        st.markdown('<div class="empty-state"><div class="icon">&#128293;</div>No trending items yet · run a poll</div>', unsafe_allow_html=True)
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-label">&#9702; Top Blog Posts by Trend</div>', unsafe_allow_html=True)
        for p in top_posts:
            st.markdown(_blog_card(p), unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-label">&#9702; Top YouTube Videos by Views</div>', unsafe_allow_html=True)
        for v in top_vids:
            st.markdown(_video_card(v), unsafe_allow_html=True)

    st.markdown('<div class="section-label">&#9702; All Trending Items (Across All Platforms)</div>', unsafe_allow_html=True)
    PLAT_ACC = {"Blog": BRAND["accent"], "YouTube": BRAND["red"],
                "Reddit": BRAND["purple"], "SerpAPI": BRAND["accent2"], "Meta Ads": BRAND["amber"]}
    for item in trending:
        ts   = float(item.get("trend_score") or 0.0)
        tc   = _trend_color(ts)
        imp  = item.get("importance", "medium")
        acc  = PLAT_ACC.get(item.get("platform",""), BRAND["accent"])
        plat = item.get("platform", "")
        comp = item.get("competitor", "")
        url  = item.get("url", "#")
        title   = item.get("title", "")
        summary = item.get("summary", "")
        date    = fdate(item.get("detected_at"))
        summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""
        plat_span2  = _mono_span("&#128225; " + plat, acc)
        score_span2 = _mono_span(f"&#9650; {ts:.2f}", tc)
        imp_tag2    = _importance_tag(imp)
        comp_tag2   = _tag(comp, "tag-comp")
        trend_bar2  = _trend_bar_html(ts, acc)
        title_c2    = BRAND["text"]
        card_html2  = (
            f'<div class="feed-card" style="border-left:3px solid {acc}">' +
            '<div class="card-eyebrow">' + comp_tag2 + plat_span2 + imp_tag2 + score_span2 + '</div>' +
            f'<div class="card-title"><a href="{url}" target="_blank" style="color:{title_c2};text-decoration:none">{title}</a></div>' +
            summary_html + trend_bar2 +
            f'<div class="card-meta"><span>{date}</span></div>' +
            '</div>'
        )
        st.markdown(card_html2, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: COMPETITIVE MATRIX
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Competitive Matrix":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#8862; Competitive Matrix</div>
  <div class="page-subtitle">Side-by-side comparison · share of voice · activity scores</div>
</div>""", unsafe_allow_html=True)

    all_posts  = pd.DataFrame(api("/api/blog-posts", {"limit":500}) or [])
    all_vids   = pd.DataFrame(api("/api/youtube",    {"limit":500}) or [])
    all_reddit = pd.DataFrame(api("/api/reddit",     {"limit":500}) or [])
    all_ads    = pd.DataFrame(api("/api/ads",         {"limit":500}) or [])
    all_serp   = pd.DataFrame(api("/api/serp",        {"limit":500}) or [])
    sent_data  = api("/api/sentiment") or {}

    matrix_rows = []
    for comp in comp_names:
        def _cnt(df_, col="competitor"):
            return len(df_[df_[col]==comp]) if not df_.empty and col in df_.columns else 0
        p_cnt  = _cnt(all_posts)
        v_cnt  = _cnt(all_vids)
        r_cnt  = _cnt(all_reddit)
        a_cnt  = _cnt(all_ads)
        s_cnt  = _cnt(all_serp)
        views  = int(pd.to_numeric(
            all_vids[all_vids["competitor"]==comp]["views"] if not all_vids.empty and "competitor" in all_vids.columns else pd.Series(),
            errors="coerce").sum())
        s_info   = sent_data.get(comp, {})
        avg_sent = round(s_info.get("avg_score", 0), 3)
        activity = round(p_cnt*3 + v_cnt*5 + r_cnt*1 + a_cnt*4 + s_cnt*2 + min(views/10000,20), 1)
        matrix_rows.append({
            "Competitor": comp, "Blog": p_cnt, "YouTube": v_cnt,
            "YT Views": fnum(views), "Reddit": r_cnt, "Ads": a_cnt,
            "SERP": s_cnt, "Avg Sentiment": f"{avg_sent:+.3f}",
            "Activity Score": activity,
        })

    if not matrix_rows:
        st.markdown('<div class="empty-state"><div class="icon">&#8862;</div>No data yet · run a poll</div>', unsafe_allow_html=True)
        st.stop()

    matrix_df = pd.DataFrame(matrix_rows).sort_values("Activity Score", ascending=False)

    # Radar chart
    st.markdown('<div class="section-label">&#9702; Activity Radar</div>', unsafe_allow_html=True)
    cats = ["Blog","YouTube","Reddit","Ads","SERP"]
    fig_r = go.Figure()
    for _, row in matrix_df.iterrows():
        raw      = [row["Blog"], row["YouTube"], row["Reddit"], row["Ads"], row["SERP"]]
        max_vals = [max(matrix_df["Blog"].max(),1), max(matrix_df["YouTube"].max(),1),
                    max(matrix_df["Reddit"].max(),1), max(matrix_df["Ads"].max(),1),
                    max(matrix_df["SERP"].max(),1)]
        vals  = [round(v/m*10,1) for v,m in zip(raw,max_vals)] + [round(raw[0]/max_vals[0]*10,1)]
        color = comp_color(row["Competitor"], comp_names)
        fig_r.add_trace(go.Scatterpolar(
            r=vals, theta=cats+[cats[0]], fill="toself", name=row["Competitor"],
            line=dict(color=color, width=2), fillcolor=color+"15",
        ))
    fig_r.update_layout(
        polar=dict(bgcolor=BRAND["surface"],
                   radialaxis=dict(visible=True, range=[0,10], gridcolor=BRAND["border"],
                                   tickfont=dict(color=BRAND["muted"],size=9)),
                   angularaxis=dict(gridcolor=BRAND["border"], tickfont=dict(color=BRAND["muted2"],size=11))),
        height=380, showlegend=True, paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=BRAND["muted2"]),
        legend=dict(font=dict(color=BRAND["muted"],size=10),bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=50,r=50,t=30,b=30),
    )
    st.plotly_chart(fig_r, use_container_width=True, config=plotly_cfg())

    # Activity bars
    st.markdown('<div class="section-label">&#9702; Activity Score Ranking</div>', unsafe_allow_html=True)
    for _, row in matrix_df.iterrows():
        max_score = matrix_df["Activity Score"].max() or 1
        pct       = int(row["Activity Score"] / max_score * 100)
        color     = comp_color(row["Competitor"], comp_names)
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:16px;padding:10px 0;border-bottom:1px solid {BRAND['border']}">
  <div style="width:130px;font-size:0.8rem;font-weight:600;color:{BRAND['text']}">{row['Competitor']}</div>
  <div style="flex:1;background:{BRAND['border']};border-radius:3px;height:6px">
    <div style="width:{pct}%;height:6px;border-radius:3px;background:{color}"></div>
  </div>
  <div style="width:60px;text-align:right;font-family:monospace;font-size:0.78rem;color:{color}">{row['Activity Score']}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">&#9702; Full Matrix</div>', unsafe_allow_html=True)
    st.dataframe(matrix_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AGENT HEALTH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Agent Health":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#9881; Agent Health</div>
  <div class="page-subtitle">Run history · latency · error rates · evaluation scores</div>
</div>""", unsafe_allow_html=True)

    runs  = api("/api/runs",        {"limit": 500}) or []
    evals = api("/api/evaluations", {"limit": 50})  or []

    if not runs:
        st.markdown('<div class="empty-state"><div class="icon">&#9881;</div>No agent runs yet · trigger a poll</div>', unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(runs)
    df["run_at_dt"]   = pd.to_datetime(df["run_at"], errors="coerce")
    df["latency_ms"]  = pd.to_numeric(df.get("latency_ms",  0), errors="coerce").fillna(0)
    df["items_found"] = pd.to_numeric(df.get("items_found", 0), errors="coerce").fillna(0)

    status = df["status"].value_counts().to_dict() if "status" in df.columns else {}
    err_rate = round(int(status.get("error",0)) / max(len(df),1) * 100, 1)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Runs",  len(df))
    m2.metric("&#9989; Success", int(status.get("success",0)))
    m3.metric("&#10060; Errors", int(status.get("error",0)))
    m4.metric("Error Rate",  f"{err_rate}%")
    m5.metric("Avg Latency", f"{df['latency_ms'].mean():.0f}ms")

    st.markdown("<br>", unsafe_allow_html=True)
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown('<div class="section-label">&#9702; Avg Latency by Agent (ms)</div>', unsafe_allow_html=True)
        if "agent_name" in df.columns:
            lat = df.groupby("agent_name")["latency_ms"].mean().reset_index()
            fig = go.Figure(go.Bar(x=lat["agent_name"], y=lat["latency_ms"],
                                   marker_color=BRAND["accent"], marker_line_width=0,
                                   text=lat["latency_ms"].apply(lambda x: f"{int(x)}ms"),
                                   textposition="outside",
                                   textfont=dict(color=BRAND["muted2"],size=10)))
            fig.update_layout(height=240, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg())

    with ch2:
        st.markdown('<div class="section-label">&#9702; Items Found by Agent</div>', unsafe_allow_html=True)
        if "agent_name" in df.columns:
            items = df.groupby("agent_name")["items_found"].sum().reset_index()
            fig2  = go.Figure(go.Bar(x=items["agent_name"], y=items["items_found"],
                                     marker_color=BRAND["accent2"], marker_line_width=0))
            fig2.update_layout(height=240, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig2, use_container_width=True, config=plotly_cfg())

    st.markdown('<div class="section-label">&#9702; Run Status Timeline</div>', unsafe_allow_html=True)
    df["date"]    = df["run_at_dt"].dt.date
    by_status_df  = df.groupby(["date","status"]).size().reset_index(name="count")
    fig3 = go.Figure()
    for s, color in [("success", BRAND["green"]), ("error", BRAND["red"])]:
        sub = by_status_df[by_status_df["status"]==s]
        if not sub.empty:
            fig3.add_trace(go.Bar(x=sub["date"], y=sub["count"], name=s.capitalize(),
                                  marker_color=color, marker_line_width=0))
    fig3.update_layout(barmode="stack", height=200, showlegend=True,
                       legend=dict(font=dict(color=BRAND["muted"],size=10),bgcolor="rgba(0,0,0,0)"),
                       **CHART_BASE)
    st.plotly_chart(fig3, use_container_width=True, config=plotly_cfg())

    if evals:
        st.markdown('<div class="section-label">&#9702; Evaluation Scores</div>', unsafe_allow_html=True)
        ev_df  = pd.DataFrame(evals)
        ev_df["score"] = pd.to_numeric(ev_df.get("score",0), errors="coerce")
        latest = ev_df.sort_values("evaluated_at", ascending=False).groupby("metric_name").first().reset_index()
        ecols  = st.columns(max(len(latest), 1))
        for i, (_, row) in enumerate(latest.iterrows()):
            pct   = int(row["score"] * 100)
            color = BRAND["green"] if pct>=70 else (BRAND["amber"] if pct>=40 else BRAND["red"])
            with ecols[i]:
                st.markdown(f"""
<div class="kpi-block" style="text-align:center">
  <div class="kpi-val" style="color:{color};font-size:1.8rem">{pct}%</div>
  <div class="kpi-label">{row['metric_name'].replace('_',' ')}</div>
  <div class="progress-bar" style="margin-top:10px">
    <div class="progress-fill" style="width:{pct}%;background:{color}"></div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">&#9702; Run Log</div>', unsafe_allow_html=True)
    show_cols = [c for c in ["agent_name","competitor","status","items_found","latency_ms","error_msg","run_at"] if c in df.columns]
    df_show   = df[show_cols].copy()
    df_show.columns = [c.replace("_"," ").title() for c in show_cols]
    if "Run At" in df_show.columns:
        df_show["Run At"] = df_show["Run At"].apply(fdate)
    if "Latency Ms" in df_show.columns:
        df_show["Latency Ms"] = df_show["Latency Ms"].apply(lambda x: f"{x:.0f}ms")
    st.dataframe(df_show, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MLFLOW ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "MLflow Analytics":
    st.markdown("""
<div class="page-header">
  <div class="page-title">&#9672; MLflow Analytics</div>
  <div class="page-subtitle">Experiment tracking · agent performance · token usage · latency profiling</div>
</div>""", unsafe_allow_html=True)

    days_opt = st.selectbox("Time window", [7,14,30,60,90], index=2,
                             label_visibility="collapsed",
                             format_func=lambda d: f"Last {d} days")
    stats = api("/api/mlflow-stats", {"days": days_opt}) or {}

    if not stats or not stats.get("total", {}).get("runs"):
        st.markdown('<div class="empty-state"><div class="icon">&#9672;</div>No runs logged yet · trigger a poll</div>', unsafe_allow_html=True)
        st.stop()

    total = stats.get("total", {})
    daily = stats.get("daily", [])
    by_ag = stats.get("by_agent", {})
    errs  = stats.get("recent_errors", [])

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Runs",      fnum(total.get("runs",0)))
    k2.metric("&#9989; Success Rate", f"{total.get('success_rate',0)}%")
    k3.metric("&#10060; Error Rate",  f"{total.get('error_rate',0)}%")
    k4.metric("Items Collected",  fnum(total.get("items_found",0)))
    k5.metric("Avg Latency",     f"{total.get('avg_latency_ms',0):.0f}ms")
    k6.metric("Tokens Used",     fnum(total.get("tokens_used",0)))

    st.markdown("<br>", unsafe_allow_html=True)

    if daily:
        st.markdown('<div class="section-label">&#9702; Daily Run Volume</div>', unsafe_allow_html=True)
        df_d = pd.DataFrame(daily)
        fig_v = go.Figure()
        fig_v.add_trace(go.Bar(x=df_d["date"], y=df_d["success"], name="Success",
                               marker_color=BRAND["green"], marker_line_width=0))
        fig_v.add_trace(go.Bar(x=df_d["date"], y=df_d["errors"], name="Error",
                               marker_color=BRAND["red"], marker_line_width=0))
        fig_v.update_layout(barmode="stack", height=200, showlegend=True,
                            legend=dict(font=dict(color=BRAND["muted"],size=10),bgcolor="rgba(0,0,0,0)"),
                            **CHART_BASE)
        st.plotly_chart(fig_v, use_container_width=True, config=plotly_cfg())

        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown('<div class="section-label">&#9702; Items Collected per Day</div>', unsafe_allow_html=True)
            fig_i = go.Figure(go.Scatter(x=df_d["date"], y=df_d["items"],
                                         fill="tozeroy", mode="lines",
                                         line=dict(color=BRAND["accent"],width=2),
                                         fillcolor="rgba(59,130,246,0.10)"))
            fig_i.update_layout(height=180, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig_i, use_container_width=True, config=plotly_cfg())
        with ch2:
            st.markdown('<div class="section-label">&#9702; Tokens Used per Day</div>', unsafe_allow_html=True)
            fig_t = go.Figure(go.Scatter(x=df_d["date"], y=df_d["tokens"],
                                         fill="tozeroy", mode="lines",
                                         line=dict(color=BRAND["purple"],width=2),
                                         fillcolor="rgba(139,92,246,0.10)"))
            fig_t.update_layout(height=180, showlegend=False, **CHART_BASE)
            st.plotly_chart(fig_t, use_container_width=True, config=plotly_cfg())

    if by_ag:
        st.markdown('<div class="section-label">&#9702; Per-Agent Performance</div>', unsafe_allow_html=True)
        ag_rows = [{"Agent": a, **v} for a, v in by_ag.items()]
        df_ag   = pd.DataFrame(ag_rows).sort_values("runs", ascending=False)

        ag1, ag2 = st.columns(2)
        with ag1:
            fig_l = go.Figure(go.Bar(x=df_ag["Agent"], y=df_ag["avg_latency_ms"],
                                     marker_color=BRAND["accent"], marker_line_width=0,
                                     text=df_ag["avg_latency_ms"].apply(lambda x: f"{x:.0f}ms"),
                                     textposition="outside",
                                     textfont=dict(color=BRAND["muted2"],size=10)))
            fig_l.update_layout(height=220, showlegend=False,
                                title_text="Avg Latency (ms)",
                                title_font=dict(color=BRAND["muted2"],size=11),
                                **CHART_BASE)
            st.plotly_chart(fig_l, use_container_width=True, config=plotly_cfg())
        with ag2:
            fig_items = go.Figure(go.Bar(x=df_ag["Agent"], y=df_ag["items"],
                                         marker_color=BRAND["accent2"], marker_line_width=0))
            fig_items.update_layout(height=220, showlegend=False,
                                    title_text="Items Found",
                                    title_font=dict(color=BRAND["muted2"],size=11),
                                    **CHART_BASE)
            st.plotly_chart(fig_items, use_container_width=True, config=plotly_cfg())

        disp = df_ag[["Agent","runs","success","errors","success_rate","avg_latency_ms","p95_latency_ms","items","tokens"]].copy()
        disp.columns = ["Agent","Runs","Success","Errors","Success %","Avg ms","P95 ms","Items","Tokens"]
        disp["Success %"] = disp["Success %"].apply(lambda x: f"{x}%")
        disp["Avg ms"]    = disp["Avg ms"].apply(lambda x: f"{x:.0f}ms")
        disp["P95 ms"]    = disp["P95 ms"].apply(lambda x: f"{x:.0f}ms")
        st.dataframe(disp, use_container_width=True, hide_index=True)

    if errs:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">&#9702; Recent Errors</div>', unsafe_allow_html=True)
        for err in errs[:10]:
            msg        = (err.get("error_msg") or "unknown error")[:200]
            agent      = err.get("agent","")
            comp       = err.get("competitor","")
            date       = fdate(err.get("run_at"))
            agent_span = _mono_span(agent, BRAND["red"])
            date_span  = _mono_span(date, BRAND["muted"])
            comp_tag   = _tag(comp, "tag-comp")
            red_c      = BRAND["red"]
            card_html  = (
                f'<div class="feed-card" style="border-left:2px solid {red_c}">' +
                '<div class="card-eyebrow">' + agent_span + comp_tag + date_span + '</div>' +
                f'<div style="font-family:monospace;font-size:0.72rem;color:{red_c};margin-top:6px">{msg}</div>' +
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    dh_user = os.getenv("DAGSHUB_USERNAME","")
    dh_repo = os.getenv("DAGSHUB_REPO_NAME","")
    st.markdown("<br>", unsafe_allow_html=True)
    if dh_user and dh_repo:
        st.markdown(f"""
<div class="alert-banner" style="border-color:rgba(59,130,246,0.3);background:rgba(59,130,246,0.05)">
  <div class="alert-title">&#128279; DagsHub MLflow UI</div>
  View full experiment history at
  <a href="https://dagshub.com/{dh_user}/{dh_repo}.mlflow" target="_blank"
     style="color:{BRAND['accent']}">dagshub.com/{dh_user}/{dh_repo}.mlflow</a>
</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div class="alert-banner">
  <div class="alert-title">&#8505; Connect DagsHub for full MLflow UI</div>
  Add <code>DAGSHUB_USERNAME</code>, <code>DAGSHUB_REPO_NAME</code>, <code>DAGSHUB_TOKEN</code>
  to <code>.env</code> to sync all runs to DagsHub.
</div>""", unsafe_allow_html=True)
