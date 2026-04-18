import smtplib
import logging
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import get_settings, get_alert_config

logger = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "high":   {"emoji": "🔴", "color": "#EF4444"},
    "medium": {"emoji": "🟠", "color": "#F59E0B"},
    "low":    {"emoji": "🟢", "color": "#10B981"},
}

def _severity(importance: str, trend_score: float = 0.0) -> str:
    if importance in SEVERITY_COLORS:
        return importance
    if trend_score >= 0.7:
        return "high"
    if trend_score >= 0.4:
        return "medium"
    return "low"


# ── Email ─────────────────────────────────────────────────────────────────────

_STYLE = """
<style>
  body { margin:0; padding:0; background:#f4f6f8; font-family:'Segoe UI',Arial,sans-serif; color:#1a1a2e; }
  .wrap { max-width:680px; margin:0 auto; padding:24px 16px; }
  .header { background:#1a1a2e; border-radius:10px 10px 0 0; padding:24px 28px; }
  .header h1 { margin:0; font-size:20px; color:#3B82F6; }
  .header p { margin:6px 0 0; font-size:12px; color:#8892a4; }
  .body { background:#fff; border:1px solid #e2e8f0; border-top:none; border-radius:0 0 10px 10px; padding:24px 28px; }
  .summary-bar { background:#f8fafc; border-left:4px solid #3B82F6; padding:12px 16px; margin-bottom:20px; border-radius:0 6px 6px 0; font-size:13px; color:#475569; }
  .item { border:1px solid #e2e8f0; border-radius:8px; padding:16px; margin-bottom:14px; }
  .item-high   { border-left:4px solid #EF4444; }
  .item-medium { border-left:4px solid #F59E0B; }
  .item-low    { border-left:4px solid #10B981; }
  .badge { display:inline-block; font-size:10px; font-weight:700; padding:2px 8px; border-radius:4px; text-transform:uppercase; margin-right:4px; }
  .badge-platform { background:#EFF6FF; color:#3B82F6; }
  .badge-high   { background:#FEF2F2; color:#EF4444; }
  .badge-medium { background:#FFFBEB; color:#D97706; }
  .badge-low    { background:#F0FDF4; color:#16A34A; }
  .item-title { font-size:15px; font-weight:600; color:#0f172a; margin:10px 0 6px; line-height:1.4; }
  .item-summary { font-size:13px; color:#475569; line-height:1.6; margin-bottom:8px; }
  .item-insights { font-size:12px; color:#64748b; background:#f8fafc; padding:8px 12px; border-radius:4px; margin-bottom:8px; }
  .item-meta { font-size:11px; color:#94a3b8; margin-top:8px; }
  .btn { display:inline-block; background:#3B82F6; color:#fff !important; text-decoration:none; padding:8px 18px; border-radius:6px; font-size:13px; font-weight:600; margin-top:10px; }
  .tags { margin-top:8px; }
  .tag { display:inline-block; background:#f1f5f9; color:#64748b; font-size:10px; padding:2px 7px; border-radius:3px; margin:2px; }
  .footer { text-align:center; font-size:11px; color:#94a3b8; margin-top:20px; }
</style>
"""

def _render_item(item: dict) -> str:
    sev    = _severity(item.get("importance","medium"), item.get("trend_score", 0.0))
    cfg    = SEVERITY_COLORS[sev]
    ts     = item.get("trend_score", 0.0) or 0.0
    tags   = item.get("keywords") or []
    tags_html = (
        '<div class="tags">' +
        "".join(f'<span class="tag">{t}</span>' for t in tags[:5]) +
        "</div>"
    ) if tags else ""
    insights_html = (
        f'<div class="item-insights">💡 {item["key_insights"]}</div>'
        if item.get("key_insights") else ""
    )
    why_html = (
        f'<div class="item-insights">🎯 {item["why_it_matters"]}</div>'
        if item.get("why_it_matters") else ""
    )
    return f"""
<div class="item item-{sev}">
  <div>
    <span class="badge badge-{sev}">{cfg['emoji']} {sev}</span>
    <span class="badge badge-platform">{item.get('platform','')}</span>
  </div>
  <div class="item-title">{item.get('title','')}</div>
  <div class="item-summary">{item.get('summary','')}</div>
  {insights_html}{why_html}{tags_html}
  <div class="item-meta">Trend score: <strong>{ts:.2f}</strong></div>
  <a class="btn" href="{item.get('url','#')}">View →</a>
</div>"""


def build_digest_email(competitor: str, sections: dict[str, list[dict]]) -> str:
    """
    Build a single digest email grouping all platforms for one competitor.
    sections = {"Blog": [...], "YouTube": [...], "Meta Ads": [...], ...}
    """
    total = sum(len(v) for v in sections.values())
    now   = datetime.utcnow().strftime("%b %d %Y %H:%M UTC")

    platform_counts = ", ".join(
        f"{len(v)} {k}" for k, v in sections.items() if v
    )
    summary_bar = f'<div class="summary-bar"><strong>{total} new signal(s)</strong> detected for {competitor} — {platform_counts}</div>'

    body_html = ""
    for platform, items in sections.items():
        if not items:
            continue
        body_html += f'<p style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#94a3b8;margin:20px 0 8px">{platform}</p>'
        for item in items:
            body_html += _render_item(item)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_STYLE}</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>◈ Competitor Intelligence</h1>
    <p>{competitor} · {now}</p>
  </div>
  <div class="body">
    {summary_bar}
    {body_html}
  </div>
  <div class="footer">Competitor Intelligence Platform · Do not reply</div>
</div>
</body>
</html>"""


# ── Slack ─────────────────────────────────────────────────────────────────────

def build_slack_digest(competitor: str, sections: dict[str, list[dict]]) -> dict:
    total  = sum(len(v) for v in sections.values())
    now    = datetime.utcnow().strftime("%b %d %Y %H:%M UTC")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"◈ {competitor} — {total} new signal(s)", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"*Time:* {now}"}]},
        {"type": "divider"},
    ]
    for platform, items in sections.items():
        for item in items[:3]:
            sev     = _severity(item.get("importance","medium"), item.get("trend_score", 0.0))
            emoji   = SEVERITY_COLORS[sev]["emoji"]
            summary = item.get("summary","")[:200]
            text    = f"{emoji} *{item.get('title','')}*\n_{summary}_\n📊 Trend: *{item.get('trend_score',0.0):.2f}* · {platform}"
            block   = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
            if item.get("url"):
                block["accessory"] = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View →"},
                    "url": item["url"],
                    "style": "primary",
                }
            blocks.append(block)
    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": f"📍 {total} item(s) across {len([v for v in sections.values() if v])} platform(s)"}
    ]})
    return {"blocks": blocks}


# ── Transport ─────────────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str):
    settings = get_settings()
    cfg      = get_alert_config().get("email", {})
    if not cfg.get("enabled") or not settings.smtp_password:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Competitor Intel] {subject}"
        msg["From"]    = settings.alert_email_from
        msg["To"]      = settings.alert_email_to
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"), cfg.get("smtp_port", 587)) as s:
            s.starttls()
            s.login(settings.alert_email_from, settings.smtp_password)
            s.sendmail(settings.alert_email_from, settings.alert_email_to, msg.as_string())
        logger.info(f"Email sent: {subject}")
    except Exception as e:
        logger.error(f"Email failed: {e}")


def send_slack(payload: dict):
    url = get_settings().slack_webhook_url
    if not url:
        return
    try:
        requests.post(url, json=payload, timeout=10)
        logger.info("Slack alert sent")
    except Exception as e:
        logger.error(f"Slack failed: {e}")


# ── Public API (called by scheduler) ─────────────────────────────────────────
# All individual alert_* functions collect their item and store it in a
# per-poll digest buffer. The scheduler calls flush_digest() once per
# competitor after all agents run, sending a single email.

_digest_buffer: dict[str, dict[str, list]] = {}


def _buffer(competitor: str, platform: str, item: dict):
    if competitor not in _digest_buffer:
        _digest_buffer[competitor] = {}
    _digest_buffer[competitor].setdefault(platform, []).append(item)


def alert_new_blog_post(competitor, title, url, sentiment,
                        summary="", key_insights="", why_it_matters="",
                        trend_score=0.0, importance="medium", keywords=None):
    if not get_alert_config().get("triggers", {}).get("new_blog_post", True):
        return
    _buffer(competitor, "Blog", dict(
        competitor=competitor, platform="Blog", title=title, url=url,
        summary=summary or f"New blog post from {competitor}",
        sentiment_label=sentiment, key_insights=key_insights,
        why_it_matters=why_it_matters, trend_score=trend_score,
        importance=importance, keywords=keywords or [],
    ))


def alert_new_youtube_video(competitor, title, url, views,
                             summary="", trend_score=0.0, importance="medium"):
    if not get_alert_config().get("triggers", {}).get("new_youtube_video", True):
        return
    _buffer(competitor, "YouTube", dict(
        competitor=competitor, platform="YouTube", title=title, url=url,
        summary=summary or f"New video from {competitor} — {views:,} views",
        why_it_matters=f"{views:,} views — monitor for reach and messaging.",
        trend_score=trend_score, importance=importance,
    ))


def alert_new_ad(competitor, ad_id, body_preview, headline="", cta="",
                 platform="Facebook", landing_url="", ad_type="", ad_summary=""):
    if not get_alert_config().get("triggers", {}).get("new_ad_detected", True):
        return
    _buffer(competitor, "Meta Ads", dict(
        competitor=competitor, platform=f"Meta Ads ({platform})",
        title=headline or f"New ad from {competitor}",
        url=landing_url or "#",
        summary=ad_summary or body_preview[:200],
        key_insights=f"CTA: {cta}" if cta else "",
        why_it_matters=f"Ad type: {ad_type}. Monitor messaging strategy." if ad_type else "",
        trend_score=0.5, importance="medium",
    ))


def alert_new_serp_result(competitor, result_type, title, url,
                          summary="", key_insights="", why_it_matters="",
                          trend_score=0.0, importance="medium"):
    _buffer(competitor, f"SerpAPI ({result_type})", dict(
        competitor=competitor, platform=f"SerpAPI ({result_type})",
        title=title, url=url, summary=summary,
        key_insights=key_insights, why_it_matters=why_it_matters,
        trend_score=trend_score, importance=importance,
    ))


def alert_sentiment_drop(competitor, score):
    threshold = get_alert_config().get("triggers", {}).get("sentiment_drop_threshold", -0.3)
    if score > threshold:
        return
    _buffer(competitor, "Sentiment", dict(
        competitor=competitor, platform="Sentiment",
        title=f"Sentiment drop: {competitor}",
        url="#",
        summary=f"Avg sentiment dropped to {score:.2f} — public perception may be declining.",
        trend_score=abs(score), importance="high",
    ))


def flush_digest(competitor: str):
    """Send one digest email+slack per competitor then clear the buffer."""
    sections = _digest_buffer.pop(competitor, {})
    if not sections:
        return
    total = sum(len(v) for v in sections.values())
    if total == 0:
        return
    sev_label = "high" if any(
        i.get("importance") == "high" or (i.get("trend_score") or 0) >= 0.7
        for items in sections.values() for i in items
    ) else "medium"
    emoji   = SEVERITY_COLORS[sev_label]["emoji"]
    subject = f"{emoji} {total} new signal(s) · {competitor}"

    send_email(subject, build_digest_email(competitor, sections))
    send_slack(build_slack_digest(competitor, sections))
    logger.info(f"Digest sent for {competitor}: {total} item(s) across {list(sections.keys())}")
