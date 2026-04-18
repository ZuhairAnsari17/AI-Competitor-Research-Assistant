import logging
from datetime import datetime
import feedparser
from sqlalchemy.orm import Session
from app.core.database import BlogPost
from app.core.llm import call_llm
from app.core.tracking import track_agent_run

logger = logging.getLogger(__name__)


def _analyse(title: str, content: str, competitor: str) -> tuple[dict, int]:
    prompt = f"""Analyse this blog post from {competitor}. Return JSON only.

Title: {title}
Content: {content[:600]}

{{
  "summary": "one sentence — what this is and why it matters competitively",
  "key_insights": "2-3 takeaways separated by ' | '",
  "why_it_matters": "one sentence on competitive implication",
  "strategy_insight": "what this reveals about {competitor}'s direction",
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "positive|neutral|negative",
  "keywords": ["kw1","kw2","kw3"],
  "trend_score": <float 0.0-1.0>,
  "importance": "high|medium|low",
  "category": "product_launch|research|company_update|partnership|hiring|marketing|other"
}}"""
    return call_llm(prompt, max_tokens=400, json_mode=True)


def run_blog_agent(competitor: dict, db: Session) -> dict:
    name      = competitor["name"]
    feeds     = competitor.get("rss_feeds", [])
    new_posts = 0
    total_tok = 0

    with track_agent_run("blog_monitor", name, {"feed_count": len(feeds)}) as metrics:
        for feed_url in feeds:
            try:
                for entry in feedparser.parse(feed_url).entries[:10]:
                    url = entry.get("link", "")
                    if not url or db.query(BlogPost).filter_by(url=url).first():
                        continue

                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])

                    title   = entry.get("title", "No title")
                    content = entry.get("summary", "")
                    a, tok  = _analyse(title, content, name)
                    total_tok += tok

                    db.add(BlogPost(
                        competitor=name, title=title, url=url, published_at=published,
                        summary=a.get("summary") or content[:300],
                        key_insights=a.get("key_insights", ""),
                        why_it_matters=a.get("why_it_matters", ""),
                        strategy_insight=a.get("strategy_insight", ""),
                        sentiment_score=float(a.get("sentiment_score", 0.0)),
                        sentiment_label=a.get("sentiment_label", "neutral"),
                        keywords=a.get("keywords", []),
                        trend_score=float(a.get("trend_score", 0.3)),
                        importance=a.get("importance", "medium"),
                        source="rss",
                    ))
                    new_posts += 1
                    logger.info(f"Blog [{name}]: {title[:70]} (trend={a.get('trend_score',0):.2f})")
            except Exception as e:
                logger.error(f"Blog feed error [{feed_url}]: {e}")

        db.commit()
        metrics["blog_posts_found"] = new_posts
        metrics["total_tokens_used"] = total_tok
        metrics["items_found"] = new_posts

    return {"new_posts": new_posts, "competitor": name}
