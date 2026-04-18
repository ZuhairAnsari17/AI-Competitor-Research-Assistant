"""
YouTube Agent — RSS + YouTube Data API v3 + LLM enrichment.

Fetch strategy:
  1. YouTube public RSS feed (no key needed, but blocked on some server IPs)
  2. YouTube Data API v3 via uploads playlist (fallback when RSS fails)

LLM generates: summary, category, trend_score, sentiment.
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import YouTubeVideo
from app.core.llm import call_llm
from app.core.tracking import track_agent_run

logger = logging.getLogger(__name__)

YT_RSS_BASE = "https://www.youtube.com/feeds/videos.xml"
YT_API_BASE = "https://www.googleapis.com/youtube/v3"

ATOM_NS  = "http://www.w3.org/2005/Atom"
MEDIA_NS = "http://search.yahoo.com/mrss/"
YT_NS    = "http://www.youtube.com/xml/schemas/2015"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml, text/xml, */*",
}


def _fetch_rss(channel_id: str) -> tuple[list[dict], bool]:
    """
    Fetch videos from YouTube RSS. Returns (videos, success).
    success=False means RSS is blocked/unavailable — caller should try API fallback.
    """
    url = f"{YT_RSS_BASE}?channel_id={channel_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)

        if r.status_code == 404:
            logger.error(
                f"YouTube RSS 404 for channel '{channel_id}' — channel ID may be wrong. "
                f"Find the correct ID: go to the channel page → view-source → search 'channelId'. "
                f"Will try YouTube Data API fallback if YOUTUBE_API_KEY is set."
            )
            return [], False

        if r.status_code == 403:
            logger.warning(
                f"YouTube RSS 403 for channel '{channel_id}' — server IP is blocked by YouTube. "
                f"Will try YouTube Data API fallback if YOUTUBE_API_KEY is set."
            )
            return [], False

        if r.status_code != 200:
            logger.error(f"YouTube RSS HTTP {r.status_code} for channel {channel_id}")
            return [], False

        root   = ET.fromstring(r.content)
        videos = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            vid_id_el = entry.find(f"{{{YT_NS}}}videoId")
            if vid_id_el is not None and vid_id_el.text:
                vid_id = vid_id_el.text
            else:
                id_el = entry.find(f"{{{ATOM_NS}}}id")
                if id_el is not None and id_el.text:
                    vid_id = id_el.text.split(":")[-1]
                else:
                    continue

            title_el     = entry.find(f"{{{ATOM_NS}}}title")
            published_el = entry.find(f"{{{ATOM_NS}}}published")
            link_el      = entry.find(f"{{{ATOM_NS}}}link")

            title = title_el.text.strip() if (title_el is not None and title_el.text) else "(no title)"
            url_  = (
                link_el.get("href", f"https://youtube.com/watch?v={vid_id}")
                if link_el is not None
                else f"https://youtube.com/watch?v={vid_id}"
            )

            published = None
            if published_el is not None and published_el.text:
                try:
                    published = datetime.fromisoformat(
                        published_el.text.replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            views = 0
            description = ""
            media_group = entry.find(f"{{{MEDIA_NS}}}group")
            if media_group is not None:
                stats_el = media_group.find(f"{{{MEDIA_NS}}}statistics")
                if stats_el is not None:
                    views = int(stats_el.get("views", 0) or 0)
                desc_el = media_group.find(f"{{{MEDIA_NS}}}description")
                if desc_el is not None and desc_el.text:
                    description = desc_el.text[:500]

            videos.append({
                "video_id": vid_id, "title": title, "url": url_,
                "description": description, "views": views,
                "likes": 0, "comments": 0, "published": published,
            })

        logger.info(f"YouTube RSS: {len(videos)} videos for channel {channel_id}")
        return videos, True

    except ET.ParseError as e:
        logger.error(f"YouTube RSS XML parse error for {channel_id}: {e}")
        return [], False
    except Exception as e:
        logger.error(f"YouTube RSS error for {channel_id}: {e}", exc_info=True)
        return [], False


def _fetch_via_api(channel_id: str, api_key: str, max_results: int = 15) -> list[dict]:
    """
    Fallback: fetch latest videos using the YouTube Data API v3.
    Uses the channel's uploads playlist (UU + channel_id[2:]).
    Works reliably from server IPs unlike RSS.
    """
    if not api_key:
        logger.warning(
            f"YouTube [{channel_id}]: RSS failed and no YOUTUBE_API_KEY set. "
            "Add YOUTUBE_API_KEY to .env to fetch videos via the Data API."
        )
        return []

    # Uploads playlist ID = "UU" + channel_id[2:]
    playlist_id = "UU" + channel_id[2:]
    logger.info(f"YouTube API fallback: fetching uploads playlist {playlist_id}")

    try:
        r = requests.get(
            f"{YT_API_BASE}/playlistItems",
            params={
                "key":        api_key,
                "playlistId": playlist_id,
                "part":       "snippet",
                "maxResults": max_results,
            },
            timeout=15,
        )
        if r.status_code == 404:
            logger.error(
                f"YouTube API 404 for playlist {playlist_id} — "
                f"channel ID '{channel_id}' may be incorrect. "
                "Find it: go to channel page → view-source → search 'channelId'."
            )
            return []
        r.raise_for_status()

        videos = []
        for item in r.json().get("items", []):
            snip    = item.get("snippet", {})
            res_id  = snip.get("resourceId", {})
            vid_id  = res_id.get("videoId", "")
            if not vid_id:
                continue

            title       = snip.get("title", "(no title)")
            description = (snip.get("description") or "")[:500]
            published_s = snip.get("publishedAt", "")
            published   = None
            if published_s:
                try:
                    published = datetime.fromisoformat(published_s.replace("Z", "+00:00"))
                except Exception:
                    pass

            videos.append({
                "video_id":   vid_id,
                "title":      title,
                "url":        f"https://youtube.com/watch?v={vid_id}",
                "description": description,
                "views":      0,
                "likes":      0,
                "comments":   0,
                "published":  published,
            })

        logger.info(f"YouTube API fallback: {len(videos)} videos for channel {channel_id}")
        return videos

    except Exception as e:
        logger.error(f"YouTube API fallback failed for {channel_id}: {e}")
        return []


def _enrich_stats(videos: list[dict], api_key: str) -> list[dict]:
    if not videos or not api_key:
        return videos
    try:
        r = requests.get(
            f"{YT_API_BASE}/videos",
            params={"key": api_key, "id": ",".join(v["video_id"] for v in videos), "part": "statistics"},
            timeout=15,
        )
        r.raise_for_status()
        stats_map = {item["id"]: item.get("statistics", {}) for item in r.json().get("items", [])}
        for v in videos:
            s = stats_map.get(v["video_id"], {})
            v["views"]    = int(s.get("viewCount",    0) or 0)
            v["likes"]    = int(s.get("likeCount",    0) or 0)
            v["comments"] = int(s.get("commentCount", 0) or 0)
    except Exception as e:
        logger.warning(f"YouTube API stats enrichment failed: {e}")
    return videos


def _analyse_video(title: str, description: str, competitor: str) -> tuple[dict, int]:
    prompt = f"""You are a competitive intelligence analyst.
Analyse this YouTube video from {competitor} and return JSON only.

Title: {title}
Description: {description or "(no description)"}

Return exactly this JSON:
{{
  "summary": "one sentence: what this video is about and its competitive significance",
  "category": "product_launch|tutorial|company_update|research|marketing|other",
  "trend_score": <float 0.0-1.0 for competitive importance>,
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "positive|neutral|negative"
}}"""
    return call_llm(prompt, max_tokens=200, json_mode=True)


def run_youtube_agent(competitor: dict, db: Session) -> dict:
    name       = competitor["name"]
    channel_id = competitor.get("youtube_channel_id", "").strip()

    if not channel_id:
        logger.warning(f"YouTube [{name}]: youtube_channel_id not set — skipping")
        return {"new_videos": 0, "skipped": True}

    settings   = get_settings()
    api_key    = settings.youtube_api_key
    new_videos = 0
    total_tok  = 0

    with track_agent_run("youtube_monitor", name, {"channel_id": channel_id}) as metrics:
        try:
            # Try RSS first; fall back to Data API if RSS is blocked or returns 404/403
            videos, rss_ok = _fetch_rss(channel_id)

            if not videos and not rss_ok:
                videos = _fetch_via_api(channel_id, api_key)

            if not videos:
                logger.warning(f"YouTube [{name}]: no videos found via RSS or API")
                metrics["items_found"] = 0
                return {"new_videos": 0, "competitor": name}

            if api_key:
                videos = _enrich_stats(videos, api_key)

            for v in videos:
                existing = db.query(YouTubeVideo).filter_by(video_id=v["video_id"]).first()
                if existing:
                    if v["views"] > (existing.views or 0):
                        existing.views    = v["views"]
                        existing.likes    = v["likes"]
                        existing.comments = v["comments"]
                    continue

                analysis, tokens = _analyse_video(v["title"], v["description"], name)
                total_tok += tokens

                db.add(YouTubeVideo(
                    competitor   = name,
                    video_id     = v["video_id"],
                    title        = v["title"],
                    url          = v["url"],
                    views        = v["views"],
                    likes        = v["likes"],
                    comments     = v["comments"],
                    summary      = analysis.get("summary", ""),
                    category     = analysis.get("category", "other"),
                    trend_score  = float(analysis.get("trend_score", 0.3)),
                    published_at = v["published"],
                ))
                new_videos += 1
                logger.info(
                    f"YouTube [{name}]: '{v['title'][:60]}' "
                    f"views={v['views']} cat={analysis.get('category','?')} "
                    f"trend={analysis.get('trend_score',0):.2f}"
                )

            db.commit()
            metrics["youtube_videos_found"] = new_videos
            metrics["total_tokens_used"]    = total_tok
            metrics["items_found"]          = new_videos

            if new_videos:
                recent = (
                    db.query(YouTubeVideo).filter_by(competitor=name)
                    .order_by(YouTubeVideo.detected_at.desc()).limit(10).all()
                )
                trends = [r.trend_score for r in recent if r.trend_score is not None]
                if trends:
                    metrics["avg_trend_score"] = round(sum(trends) / len(trends), 3)

        except Exception as e:
            logger.error(f"YouTube [{name}]: error — {e}", exc_info=True)
            metrics["error"] = str(e)
            raise

    return {"new_videos": new_videos, "competitor": name}
