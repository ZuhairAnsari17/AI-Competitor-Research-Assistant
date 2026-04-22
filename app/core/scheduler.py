import asyncio
import logging
import time
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

load_dotenv()

from app.core.config import get_config, get_competitors, invalidate_config_cache
from app.core.database import SessionLocal, AgentRun, init_db
from app.core.tracking import setup_mlflow
from app.agents.blog_agent import run_blog_agent
from app.agents.youtube_agent import run_youtube_agent
from app.agents.reddit_agent import run_reddit_agent
from app.agents.serp_agent import run_serp_agent
from app.agents.alert_service import (
    alert_new_blog_post, alert_new_youtube_video,
    alert_new_serp_result, flush_digest,
)
from app.evaluator.evaluator import run_evaluation

logger       = logging.getLogger(__name__)
scheduler    = AsyncIOScheduler()
poll_counter = 0


async def run_all_agents():
    global poll_counter
    poll_counter += 1

    invalidate_config_cache()
    competitors = get_competitors()
    logger.info(f"=== Poll #{poll_counter} — {', '.join(c['name'] for c in competitors)} ===")

    db: Session = SessionLocal()
    try:
        for competitor in competitors:
            name = competitor["name"]
            logger.info(f"--- {name} ---")

            await _run_agent(db, "blog_monitor",     name, lambda c=competitor: run_blog_agent(c, db),     "new_posts",         lambda r, n=name: _alert_blogs(db, n))
            await _run_agent(db, "youtube_monitor",  name, lambda c=competitor: run_youtube_agent(c, db),  "new_videos",        lambda r, n=name: _alert_videos(db, n))
            await _run_agent(db, "reddit_monitor",   name, lambda c=competitor: run_reddit_agent(c, db),   "mentions")
            await _run_agent(db, "serp_monitor",     name, lambda c=competitor: run_serp_agent(c, db),     "serp_results_found", lambda r, n=name: _alert_serp(db, n))

            # One digest email per competitor covering all platforms
            flush_digest(name)

        cfg        = get_config()
        eval_every = cfg.get("evaluation", {}).get("run_every_n_polls", 6)
        if poll_counter % eval_every == 0:
            try:
                run_evaluation(db)
            except Exception as e:
                logger.error(f"Evaluation error: {e}")

    finally:
        db.close()

    logger.info(f"=== Poll #{poll_counter} complete ===")


async def _run_agent(db, agent_name, competitor, fn, result_key, alert_fn=None):
    t0 = time.time()
    try:
        result  = await asyncio.get_event_loop().run_in_executor(None, fn)
        items   = result.get(result_key, 0) or 0
        elapsed = time.time() - t0

        _log_run(db, agent_name, competitor, "success", items, elapsed, result.get("error"))
        logger.info(f"  {agent_name} [{competitor}]: {items} new items in {elapsed*1000:.0f}ms")

        if items > 0 and alert_fn:
            try:
                alert_fn(result)
            except Exception as e:
                logger.warning(f"Alert prep failed [{agent_name}]: {e}")

    except Exception as e:
        elapsed = time.time() - t0
        try:
            db.rollback()
        except Exception:
            pass
        try:
            _log_run(db, agent_name, competitor, "error", 0, elapsed, str(e))
        except Exception:
            pass
        logger.error(f"  {agent_name} [{competitor}]: ERROR — {e}")


# ── Alert collectors (add to digest buffer, don't send yet) ──────────────────

def _alert_blogs(db, name):
    from app.core.database import BlogPost
    rows = db.query(BlogPost).filter_by(competitor=name, alerted=False).all()
    for p in rows:
        alert_new_blog_post(
            competitor=name, title=p.title, url=p.url,
            sentiment=p.sentiment_label or "neutral",
            summary=p.summary or "", key_insights=p.key_insights or "",
            why_it_matters=p.why_it_matters or "",
            trend_score=p.trend_score or 0.0,
            importance=p.importance or "medium",
            keywords=p.keywords or [],
        )
        p.alerted = True
    db.commit()


def _alert_videos(db, name):
    from app.core.database import YouTubeVideo
    rows = db.query(YouTubeVideo).filter_by(competitor=name, alerted=False).all()
    for v in rows:
        alert_new_youtube_video(
            competitor=name, title=v.title, url=v.url, views=v.views,
            summary=v.summary or "", trend_score=v.trend_score or 0.0,
            importance="high" if (v.trend_score or 0) >= 0.7 else "medium",
        )
        v.alerted = True
    db.commit()




def _alert_serp(db, name):
    from app.core.database import SerpResult
    rows = db.query(SerpResult).filter_by(competitor=name, alerted=False).all()
    for r in rows:
        if (r.trend_score or 0) >= 0.5 or r.importance == "high":
            alert_new_serp_result(
                competitor=name, result_type=r.result_type,
                title=r.title, url=r.url,
                summary=r.summary or "", key_insights=r.key_insights or "",
                why_it_matters=r.why_it_matters or "",
                trend_score=r.trend_score or 0.0,
                importance=r.importance or "medium",
            )
        r.alerted = True
    db.commit()


def _log_run(db, agent, competitor, status, items, elapsed, error=None):
    try:
        db.add(AgentRun(
            agent_name  = agent,
            competitor  = competitor,
            status      = status,
            items_found = items,
            latency_ms  = round(elapsed * 1000, 2),
            error_msg   = str(error)[:500] if error else None,
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise


def start_scheduler():
    cfg      = get_config()
    interval = cfg.get("app", {}).get("poll_interval_minutes", 30)
    try:
        setup_mlflow()
    except Exception as e:
        logger.warning(f"MLflow setup skipped: {e}")
    init_db()
    scheduler.add_job(
        run_all_agents,
        trigger=IntervalTrigger(minutes=interval),
        id="main_poll",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"Scheduler started — polling every {interval} minutes")


def stop_scheduler():
    scheduler.shutdown(wait=False)
