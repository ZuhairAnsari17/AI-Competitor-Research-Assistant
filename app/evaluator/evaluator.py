import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.config import get_competitors, get_config, get_settings
from app.core.database import BlogPost, YouTubeVideo, RedditMention, AgentRun, EvalResult
from groq import Groq
import json

logger = logging.getLogger(__name__)


def run_evaluation(db: Session) -> dict:
    import mlflow
    cfg = get_config()
    eval_cfg = cfg.get("evaluation", {})
    if not eval_cfg.get("enabled", True):
        return {}

    settings = get_settings()
    competitors = get_competitors()
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=3)
    results = {}

    with mlflow.start_run(run_name=f"evaluation_{int(now.timestamp())}"):
        mlflow.set_tag("run_type", "evaluation")

        # 1. Coverage score — did all sources get polled?
        total_sources = sum(len(c.get("rss_feeds", [])) + (1 if c.get("youtube_channel_id") else 0) for c in competitors)
        recent_runs = db.query(AgentRun).filter(AgentRun.run_at >= cutoff, AgentRun.status == "success").all()
        successful = len(recent_runs)
        coverage = round(min(successful / max(total_sources, 1), 1.0), 2)
        results["coverage_score"] = coverage
        mlflow.log_metric("eval_coverage_score", coverage)
        _save_eval(db, "coverage_score", coverage, {"successful_runs": successful, "total_sources": total_sources})

        # 2. Data freshness — are blog posts recent?
        fresh_count = 0
        for comp in competitors:
            recent_post = db.query(BlogPost).filter(
                BlogPost.competitor == comp["name"],
                BlogPost.detected_at >= now - timedelta(hours=25)
            ).count()
            if recent_post > 0:
                fresh_count += 1
        freshness = round(fresh_count / max(len(competitors), 1), 2)
        results["data_freshness"] = freshness
        mlflow.log_metric("eval_data_freshness", freshness)
        _save_eval(db, "data_freshness", freshness, {"fresh_competitors": fresh_count})

        # 3. Sentiment accuracy — use Groq to spot-check a few labels
        accuracy = _spot_check_sentiment(db, settings)
        results["sentiment_accuracy"] = accuracy
        mlflow.log_metric("eval_sentiment_accuracy", accuracy)
        _save_eval(db, "sentiment_accuracy", accuracy, {})

        # 4. Alert precision — were alerts sent for genuinely new content?
        new_unalerted = db.query(BlogPost).filter(BlogPost.alerted == False).count()
        precision = 1.0 if new_unalerted == 0 else round(1 - min(new_unalerted / 10, 1), 2)
        results["alert_precision"] = precision
        mlflow.log_metric("eval_alert_precision", precision)
        _save_eval(db, "alert_precision", precision, {"unalerted_posts": new_unalerted})

        # Overall score
        overall = round(sum(results.values()) / len(results), 2)
        results["overall_score"] = overall
        mlflow.log_metric("eval_overall_score", overall)

    logger.info(f"Evaluation complete: {results}")
    return results


def _spot_check_sentiment(db: Session, settings) -> float:
    if not settings.groq_api_key:
        return 0.5
    try:
        client = Groq(api_key=settings.groq_api_key)
        posts = db.query(BlogPost).filter(BlogPost.sentiment_label != None).order_by(
            BlogPost.detected_at.desc()).limit(5).all()
        if not posts:
            return 1.0

        correct = 0
        for post in posts:
            prompt = f"""Is this title sentiment positive, neutral, or negative? Return JSON: {{"sentiment": "positive|neutral|negative"}}
Title: {post.title}"""
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            if data.get("sentiment") == post.sentiment_label:
                correct += 1

        return round(correct / len(posts), 2)
    except Exception as e:
        logger.warning(f"Sentiment spot-check failed: {e}")
        return 0.5


def _save_eval(db: Session, metric: str, score: float, details: dict):
    result = EvalResult(metric_name=metric, score=score, details=details)
    db.add(result)
    db.commit()
