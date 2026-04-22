
# Competitor Intelligence API — FastAPI backend.
# Serves all dashboard data with explicit dict serialization.

import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.aws_secrets import load_aws_secrets
from app.core.config import (
    get_config, get_competitors, get_active_competitor_names,
    invalidate_config_cache,
)
from app.core.database import (
    init_db, get_db, BlogPost, YouTubeVideo,
    RedditMention, SerpResult, AgentRun, EvalResult,
)
from app.core.scheduler import start_scheduler, stop_scheduler, run_all_agents
from app.core.tracking import setup_mlflow
from app.core.logging_config import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_aws_secrets() #aws secrets might have rotated while the app was running, so we reload them on each startup
    init_db()
    try:
        setup_mlflow()
    except Exception as e:
        logger.warning(f"MLflow setup skipped: {e}")
    start_scheduler()
    asyncio.create_task(run_all_agents())
    yield
    stop_scheduler()


cfg = get_config()
app = FastAPI(title=cfg["app"]["name"], version=cfg["app"]["version"], lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app)


def _active_filter(q, model):
    names = get_active_competitor_names()
    if names:
        q = q.filter(model.competitor.in_(names))
    return q


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status":  "ok" if db_ok else "degraded",
        "version": cfg["app"]["version"],
        "db":      "ok" if db_ok else "error",
        "time":    datetime.utcnow().isoformat(),
        "competitors_configured": len(get_competitors()),
    }


# ── Summary ────────────────────────────────────────────────────────────────────

@app.get("/api/summary", tags=["Dashboard"])
def summary(db: Session = Depends(get_db)):
    since_7d  = datetime.utcnow() - timedelta(days=7)
    since_30d = datetime.utcnow() - timedelta(days=30)
    names     = get_active_competitor_names()

    def cnt(model, since):
        q = db.query(model).filter(model.detected_at >= since)
        if names:
            q = q.filter(model.competitor.in_(names))
        return q.count()

    last_run    = db.query(func.max(AgentRun.run_at)).scalar()
    recent_runs = db.query(AgentRun).order_by(desc(AgentRun.run_at)).limit(50).all()
    err_rate    = round(
        sum(1 for r in recent_runs if r.status == "error") / max(len(recent_runs), 1) * 100, 1
    )

    # Trending competitor — most items in last 7 days
    trending_comp = None
    max_items = 0
    for name in names:
        total = (
            db.query(BlogPost).filter(BlogPost.competitor == name, BlogPost.detected_at >= since_7d).count() +
            db.query(YouTubeVideo).filter(YouTubeVideo.competitor == name, YouTubeVideo.detected_at >= since_7d).count() +
            db.query(RedditMention).filter(RedditMention.competitor == name, RedditMention.detected_at >= since_7d).count()
        )
        if total > max_items:
            max_items, trending_comp = total, name

    # Most active platform
    platform_counts = {
        "Blog":    cnt(BlogPost, since_7d),
        "YouTube": cnt(YouTubeVideo, since_7d),
        "Reddit":  cnt(RedditMention, since_7d),
        "Ads":     0,
        "SerpAPI": cnt(SerpResult, since_7d),
    }
    most_active_platform = max(platform_counts, key=platform_counts.get) if platform_counts else "—"

    return {
        "blog_posts_7d":       platform_counts["Blog"],
        "blog_posts_30d":      cnt(BlogPost, since_30d),
        "youtube_videos_7d":   platform_counts["YouTube"],
        "reddit_mentions_7d":  platform_counts["Reddit"],
        "ads_detected_7d":     0,
        "serp_results_7d":     platform_counts["SerpAPI"],
        "competitors_tracked": len(get_competitors()),
        "last_poll":           last_run,
        "agent_error_rate":    err_rate,
        "trending_competitor": trending_comp,
        "most_active_platform": most_active_platform,
        "platform_counts":     platform_counts,
    }


# ── Blog Posts ─────────────────────────────────────────────────────────────────

@app.get("/api/blog-posts", tags=["Content"])
def blog_posts(
    competitor: str = None, limit: int = Query(50, le=500),
    sentiment: str = None, days: int = None,
    db: Session = Depends(get_db),
):
    q = db.query(BlogPost).order_by(desc(BlogPost.detected_at))
    q = _active_filter(q, BlogPost)
    if competitor:
        q = q.filter(BlogPost.competitor == competitor)
    if sentiment:
        q = q.filter(BlogPost.sentiment_label == sentiment)
    if days:
        q = q.filter(BlogPost.detected_at >= datetime.utcnow() - timedelta(days=days))
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id, "competitor": r.competitor, "title": r.title,
            "url": r.url, "published_at": r.published_at.isoformat() if r.published_at else None,
            "summary": r.summary or "", "key_insights": r.key_insights or "",
            "why_it_matters": r.why_it_matters or "", "strategy_insight": r.strategy_insight or "",
            "sentiment_score": r.sentiment_score, "sentiment_label": r.sentiment_label,
            "keywords": r.keywords or [], "trend_score": r.trend_score or 0.0,
            "importance": r.importance or "medium", "source": r.source or "rss",
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]


# ── YouTube ────────────────────────────────────────────────────────────────────

@app.get("/api/youtube", tags=["Content"])
def youtube_videos(
    competitor: str = None, limit: int = Query(50, le=500),
    sort: str = "newest", db: Session = Depends(get_db),
):
    q = db.query(YouTubeVideo)
    q = _active_filter(q, YouTubeVideo)
    if competitor:
        q = q.filter(YouTubeVideo.competitor == competitor)
    if sort == "views":
        q = q.order_by(desc(YouTubeVideo.views))
    elif sort == "trend":
        q = q.order_by(desc(YouTubeVideo.trend_score))
    else:
        q = q.order_by(desc(YouTubeVideo.detected_at))
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id, "competitor": r.competitor, "video_id": r.video_id,
            "title": r.title, "url": r.url, "views": r.views, "likes": r.likes,
            "comments": r.comments, "summary": r.summary or "",
            "category": r.category or "", "trend_score": r.trend_score or 0.0,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]


# ── Reddit ─────────────────────────────────────────────────────────────────────

@app.get("/api/reddit", tags=["Content"])
def reddit_mentions(
    competitor: str = None, limit: int = Query(50, le=500),
    sentiment: str = None, subreddit: str = None,
    db: Session = Depends(get_db),
):
    q = db.query(RedditMention).order_by(desc(RedditMention.detected_at))
    q = _active_filter(q, RedditMention)
    if competitor:
        q = q.filter(RedditMention.competitor == competitor)
    if sentiment:
        q = q.filter(RedditMention.sentiment_label == sentiment)
    if subreddit:
        q = q.filter(RedditMention.subreddit == subreddit)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id, "competitor": r.competitor, "post_id": r.post_id,
            "title": r.title, "url": r.url, "subreddit": r.subreddit,
            "score": r.score, "num_comments": r.num_comments,
            "sentiment_score": r.sentiment_score, "sentiment_label": r.sentiment_label,
            "summary": r.summary or "", "topic": r.topic or "",
            "trend_score": r.trend_score or 0.0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]




# ── SerpAPI Results ────────────────────────────────────────────────────────────

@app.get("/api/serp", tags=["Content"])
def serp_results(
    competitor: str = None, result_type: str = None,
    limit: int = Query(50, le=500), days: int = None,
    db: Session = Depends(get_db),
):
    q = db.query(SerpResult).order_by(desc(SerpResult.detected_at))
    q = _active_filter(q, SerpResult)
    if competitor:
        q = q.filter(SerpResult.competitor == competitor)
    if result_type:
        q = q.filter(SerpResult.result_type == result_type)
    if days:
        q = q.filter(SerpResult.detected_at >= datetime.utcnow() - timedelta(days=days))
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id, "competitor": r.competitor, "result_type": r.result_type,
            "title": r.title, "url": r.url, "snippet": r.snippet or "",
            "source": r.source or "", "summary": r.summary or "",
            "key_insights": r.key_insights or "", "why_it_matters": r.why_it_matters or "",
            "category": r.category or "", "trend_score": r.trend_score or 0.0,
            "importance": r.importance or "medium",
            "sentiment_score": r.sentiment_score, "sentiment_label": r.sentiment_label,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]


# ── Sentiment ──────────────────────────────────────────────────────────────────

@app.get("/api/sentiment", tags=["Analytics"])
def sentiment_trends(days: int = 30, db: Session = Depends(get_db)):
    since   = datetime.utcnow() - timedelta(days=days)
    results = {}
    for comp in get_competitors():
        name  = comp["name"]
        posts = (
            db.query(RedditMention)
            .filter(RedditMention.competitor == name, RedditMention.detected_at >= since)
            .all()
        )
        scored = [p for p in posts if p.sentiment_score is not None]
        results[name] = {
            "avg_score": round(sum(p.sentiment_score for p in scored) / max(len(scored), 1), 3),
            "positive":  sum(1 for p in posts if p.sentiment_label == "positive"),
            "neutral":   sum(1 for p in posts if p.sentiment_label == "neutral"),
            "negative":  sum(1 for p in posts if p.sentiment_label == "negative"),
            "total":     len(posts),
        }
    return results


# ── Agent Runs ─────────────────────────────────────────────────────────────────

@app.get("/api/runs", tags=["System"])
def agent_runs(
    limit: int = Query(100, le=500),
    agent: str = None, status: str = None,
    db: Session = Depends(get_db),
):
    q = db.query(AgentRun).order_by(desc(AgentRun.run_at))
    if agent:
        q = q.filter(AgentRun.agent_name == agent)
    if status:
        q = q.filter(AgentRun.status == status)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id, "agent_name": r.agent_name, "competitor": r.competitor,
            "status": r.status, "items_found": r.items_found,
            "latency_ms": r.latency_ms, "tokens_used": r.tokens_used,
            "error_msg": r.error_msg,
            "run_at": r.run_at.isoformat() if r.run_at else None,
        }
        for r in rows
    ]


# ── Evaluations ────────────────────────────────────────────────────────────────

@app.get("/api/evaluations", tags=["System"])
def evaluations(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    rows = db.query(EvalResult).order_by(desc(EvalResult.evaluated_at)).limit(limit).all()
    return [
        {
            "id": r.id, "metric_name": r.metric_name, "score": r.score,
            "details": r.details,
            "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
        }
        for r in rows
    ]


# ── Competitors ────────────────────────────────────────────────────────────────

@app.get("/api/competitors", tags=["System"])
def list_competitors():
    return [
        {
            "name":             c["name"],
            "has_rss":          bool(c.get("rss_feeds")),
            "has_youtube":      bool(c.get("youtube_channel_id", "").strip()),
            "has_reddit":       bool(c.get("reddit_rss")),
            "has_serp":         bool(c.get("serp_queries")),
            "youtube_channel_id": c.get("youtube_channel_id", ""),
        }
        for c in get_competitors()
    ]


# ── MLflow Analytics ───────────────────────────────────────────────────────────

@app.get("/api/mlflow-stats", tags=["Analytics"])
def mlflow_stats(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    runs  = db.query(AgentRun).filter(AgentRun.run_at >= since).all()

    if not runs:
        return {"runs": [], "by_agent": {}, "by_competitor": {}, "daily": [], "total": {}}

    success_runs = [r for r in runs if r.status == "success"]
    error_runs   = [r for r in runs if r.status == "error"]
    total_items  = sum(r.items_found or 0 for r in runs)
    total_tokens = sum(r.tokens_used or 0 for r in runs)
    latencies    = [r.latency_ms for r in runs if r.latency_ms is not None]
    avg_latency  = round(sum(latencies) / len(latencies), 1) if latencies else 0
    p95_latency  = round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 1)

    by_agent: dict = {}
    for r in runs:
        a = r.agent_name or "unknown"
        if a not in by_agent:
            by_agent[a] = {"runs": 0, "success": 0, "errors": 0,
                           "items": 0, "tokens": 0, "latencies": []}
        by_agent[a]["runs"]   += 1
        by_agent[a]["items"]  += r.items_found or 0
        by_agent[a]["tokens"] += r.tokens_used or 0
        if r.status == "success":
            by_agent[a]["success"] += 1
        else:
            by_agent[a]["errors"] += 1
        if r.latency_ms is not None:
            by_agent[a]["latencies"].append(r.latency_ms)

    for a, d in by_agent.items():
        lats = d.pop("latencies")
        d["avg_latency_ms"] = round(sum(lats) / len(lats), 1) if lats else 0
        d["p95_latency_ms"] = round(sorted(lats)[int(len(lats) * 0.95)] if lats else 0, 1)
        d["success_rate"]   = round(d["success"] / max(d["runs"], 1) * 100, 1)
        d["error_rate"]     = round(d["errors"]  / max(d["runs"], 1) * 100, 1)

    by_competitor: dict = {}
    for r in runs:
        c = r.competitor or "unknown"
        if c not in by_competitor:
            by_competitor[c] = {"runs": 0, "success": 0, "errors": 0, "items": 0, "tokens": 0}
        by_competitor[c]["runs"]   += 1
        by_competitor[c]["items"]  += r.items_found or 0
        by_competitor[c]["tokens"] += r.tokens_used or 0
        if r.status == "success":
            by_competitor[c]["success"] += 1
        else:
            by_competitor[c]["errors"] += 1

    daily: dict = {}
    for r in runs:
        day = r.run_at.date().isoformat() if r.run_at else "unknown"
        if day not in daily:
            daily[day] = {"date": day, "runs": 0, "success": 0, "errors": 0,
                          "items": 0, "tokens": 0, "lat_sum": 0, "lat_count": 0}
        daily[day]["runs"]   += 1
        daily[day]["items"]  += r.items_found or 0
        daily[day]["tokens"] += r.tokens_used or 0
        if r.status == "success":
            daily[day]["success"] += 1
        else:
            daily[day]["errors"] += 1
        if r.latency_ms:
            daily[day]["lat_sum"]   += r.latency_ms
            daily[day]["lat_count"] += 1

    daily_list = []
    for d in sorted(daily.values(), key=lambda x: x["date"]):
        lc = d.pop("lat_count")
        ls = d.pop("lat_sum")
        d["avg_latency_ms"] = round(ls / lc, 1) if lc else 0
        daily_list.append(d)

    recent_errors = [
        {
            "agent": r.agent_name, "competitor": r.competitor,
            "error_msg": r.error_msg, "latency_ms": r.latency_ms,
            "run_at": r.run_at.isoformat() if r.run_at else None,
        }
        for r in sorted(error_runs, key=lambda x: x.run_at or datetime.min, reverse=True)[:20]
    ]

    return {
        "total": {
            "runs": len(runs), "success": len(success_runs), "errors": len(error_runs),
            "error_rate":    round(len(error_runs)   / max(len(runs), 1) * 100, 1),
            "success_rate":  round(len(success_runs) / max(len(runs), 1) * 100, 1),
            "items_found":   total_items,
            "tokens_used":   total_tokens,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
        },
        "by_agent":      by_agent,
        "by_competitor": by_competitor,
        "daily":         daily_list,
        "recent_errors": recent_errors,
    }


# ── Trigger poll ───────────────────────────────────────────────────────────────

@app.post("/api/trigger-poll", tags=["System"])
async def trigger_poll():
    asyncio.create_task(run_all_agents())
    return {"message": "Poll triggered", "time": datetime.utcnow().isoformat()}


@app.post("/api/reload-config", tags=["System"])
def reload_config():
    invalidate_config_cache()
    return {
        "message":     "Config reloaded",
        "competitors": [c["name"] for c in get_competitors()],
        "time":        datetime.utcnow().isoformat(),
    }


# ── Analytics helpers ──────────────────────────────────────────────────────────

@app.get("/api/stats/top-posts", tags=["Analytics"])
def top_posts(limit: int = 10, db: Session = Depends(get_db)):
    q = db.query(BlogPost).filter(BlogPost.trend_score.isnot(None))
    q = _active_filter(q, BlogPost)
    rows = q.order_by(desc(BlogPost.trend_score)).limit(limit).all()
    return [
        {"competitor": r.competitor, "title": r.title, "url": r.url,
         "summary": r.summary or "", "trend_score": r.trend_score,
         "importance": r.importance, "detected_at": r.detected_at.isoformat() if r.detected_at else None}
        for r in rows
    ]


@app.get("/api/stats/top-videos", tags=["Analytics"])
def top_videos(limit: int = 10, db: Session = Depends(get_db)):
    q = db.query(YouTubeVideo)
    q = _active_filter(q, YouTubeVideo)
    rows = q.order_by(desc(YouTubeVideo.views)).limit(limit).all()
    return [
        {"competitor": r.competitor, "title": r.title, "url": r.url,
         "views": r.views, "trend_score": r.trend_score,
         "detected_at": r.detected_at.isoformat() if r.detected_at else None}
        for r in rows
    ]


@app.get("/api/stats/trending", tags=["Analytics"])
def trending_items(limit: int = 20, db: Session = Depends(get_db)):
    """Top trending items across all platforms by trend_score."""
    since  = datetime.utcnow() - timedelta(days=7)
    names  = get_active_competitor_names()

    def _q(model, label):
        q = db.query(model).filter(
            model.detected_at >= since,
            model.trend_score >= 0.5,
        )
        if names:
            q = q.filter(model.competitor.in_(names))
        return q.order_by(desc(model.trend_score)).limit(limit).all(), label

    items = []
    for row, platform in [
        *[(r, "Blog")    for r in db.query(BlogPost).filter(BlogPost.detected_at >= since, BlogPost.trend_score >= 0.5, BlogPost.competitor.in_(names)).order_by(desc(BlogPost.trend_score)).limit(10).all()],
        *[(r, "Reddit")  for r in db.query(RedditMention).filter(RedditMention.detected_at >= since, RedditMention.trend_score >= 0.5, RedditMention.competitor.in_(names)).order_by(desc(RedditMention.trend_score)).limit(10).all()],
        *[(r, "SerpAPI") for r in db.query(SerpResult).filter(SerpResult.detected_at >= since, SerpResult.trend_score >= 0.5, SerpResult.competitor.in_(names)).order_by(desc(SerpResult.trend_score)).limit(10).all()],
*[(r, "YouTube") for r in db.query(YouTubeVideo).filter(YouTubeVideo.detected_at >= since, YouTubeVideo.trend_score >= 0.5, YouTubeVideo.competitor.in_(names)).order_by(desc(YouTubeVideo.trend_score)).limit(5).all()],
    ]:
        items.append({
            "platform":   platform,
            "competitor": row.competitor,
            "title":      row.title,
            "url":        getattr(row, "url", ""),
            "summary":    getattr(row, "summary", "") or "",
            "trend_score": row.trend_score or 0.0,
            "importance": getattr(row, "importance", "medium") or "medium",
            "detected_at": row.detected_at.isoformat() if row.detected_at else None,
        })

    items.sort(key=lambda x: x["trend_score"], reverse=True)
    return items[:limit]
