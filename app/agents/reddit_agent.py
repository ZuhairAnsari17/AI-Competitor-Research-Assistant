import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from sqlalchemy.orm import Session
from app.core.database import RedditMention
from app.core.llm import call_llm
from app.core.tracking import track_agent_run

logger  = logging.getLogger(__name__)
ATOM_NS = "http://www.w3.org/2005/Atom"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _post_id(atom_id: str, url: str) -> str:
    for pat in [r"t3_([a-z0-9]+)", r"/comments/([a-z0-9]+)/"]:
        m = re.search(pat, atom_id + " " + url, re.IGNORECASE)
        if m:
            return m.group(1)
    return atom_id or url


def _subreddit(url: str) -> str:
    m = re.search(r"reddit\.com/r/([^/?#]+)", url, re.IGNORECASE)
    return m.group(1) if m else "unknown"


def _analyse(title: str, competitor: str) -> tuple[dict, int]:
    prompt = f"""Analyse this Reddit post about {competitor}. Return JSON only.
Title: {title}
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "positive|neutral|negative",
  "summary": "one sentence about what is being said",
  "topic": "product_feedback|bug_report|praise|comparison|news|question|other",
  "trend_score": <float 0.0-1.0>
}}"""
    return call_llm(prompt, max_tokens=200, json_mode=True)


def _fetch(url: str) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code not in (200,):
            logger.warning(f"Reddit RSS HTTP {r.status_code} for {url}")
            return []
        root = ET.fromstring(r.content)
    except Exception as e:
        logger.error(f"Reddit RSS error [{url}]: {e}")
        return []

    entries = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        title_elem = entry.find(f"{{{ATOM_NS}}}title")
        link_elem  = entry.find(f"{{{ATOM_NS}}}link")
        id_elem    = entry.find(f"{{{ATOM_NS}}}id")
        upd = entry.find(f"{{{ATOM_NS}}}updated")
        link     = link_elem.get("href", "") if link_elem is not None else ""
        atom_id  = id_elem.text or "" if id_elem is not None else ""
        created  = None
        if upd is not None and upd.text:
            try:
                created = datetime.fromisoformat(upd.text.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass
        entries.append({
            "post_id":    _post_id(atom_id, link),
            "title":      (title_elem.text or "No title").strip() if title_elem is not None else "No title",
            "url":        link,
            "subreddit":  _subreddit(link),
            "created_at": created,
        })
    logger.info(f"Reddit RSS [{url}]: {len(entries)} entries")
    return entries


def run_reddit_agent(competitor: dict, db: Session) -> dict:
    name  = competitor["name"]
    feeds = competitor.get("reddit_rss", [])
    if not feeds:
        return {"mentions": 0, "competitor": name}

    mentions  = 0
    total_tok = 0

    with track_agent_run("reddit_monitor", name, {"feed_count": len(feeds)}) as metrics:
        for feed_url in feeds:
            for entry in _fetch(feed_url):
                if not entry["post_id"]:
                    continue
                if db.query(RedditMention).filter_by(post_id=entry["post_id"]).first():
                    continue

                a, tok = _analyse(entry["title"], name)
                total_tok += tok
                score = max(-1.0, min(1.0, float(a.get("sentiment_score", 0.0))))

                db.add(RedditMention(
                    competitor=name, post_id=entry["post_id"],
                    title=entry["title"][:500], url=entry["url"],
                    subreddit=entry["subreddit"], score=0, num_comments=0,
                    sentiment_score=score,
                    sentiment_label=a.get("sentiment_label", "neutral"),
                    summary=a.get("summary", ""),
                    topic=a.get("topic", "other"),
                    trend_score=float(a.get("trend_score", 0.3)),
                    created_at=entry["created_at"],
                ))
                mentions += 1
                logger.info(f"Reddit [{name}] r/{entry['subreddit']}: {entry['title'][:60]}")

        db.commit()
        metrics["reddit_mentions"]   = mentions
        metrics["total_tokens_used"] = total_tok
        metrics["items_found"]       = mentions

    return {"mentions": mentions, "competitor": name}
