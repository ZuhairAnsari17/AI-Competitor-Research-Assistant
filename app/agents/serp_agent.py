"""
SerpAPI Agent — competitor monitoring via Google search results.

Covers:
  1. News results      — latest competitor news
  2. Organic results   — blog posts, product pages
  3. Ads               — Google ads copy
  4. Trending topics   — related searches

Rate-limit strategy:
  - Rule-based scoring for ALL results (no LLM per item)
  - ONE batched LLM call per query for the top 3 high-signal items only
  - This reduces Groq calls from ~60-90 per poll to ~9 max (3 queries × 3 items)
"""
import logging
import time
import re
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings, get_config
from app.core.database import SerpResult
from app.core.llm import call_llm
from app.core.tracking import track_agent_run

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"

# Keywords for fast rule-based trend scoring — no LLM cost
_HIGH_KW    = ["launch", "release", "product", "raises", "acqui", "partner",
               "breach", "layoff", "shut down", "record", "gpt-", "model",
               "api", "funding", "revenue", "ipo", "ceo", "executive", "leaves",
               "announces", "unveil", "new feature", "update", "billion", "million"]
_POSITIVE_KW = ["launch", "raises", "partner", "growth", "record", "funding",
                "milestone", "expansion", "hire", "acqui", "award"]
_NEGATIVE_KW  = ["breach", "layoff", "shut down", "leaves", "exit", "sues",
                 "fined", "banned", "fail", "drop", "decline", "criticism"]

# Which result types get a small score boost
_TYPE_BOOST = {"news": 0.15, "google_ads": 0.10, "organic": 0.05, "trending": 0.0}


# ── Rule-based scorer (zero LLM calls) ───────────────────────────────────────

def _score(title: str, snippet: str, result_type: str) -> dict:
    """Score a result using keyword rules. Fast, no API cost."""
    text = (title + " " + snippet).lower()

    high_count = sum(1 for kw in _HIGH_KW if kw in text)
    pos_count  = sum(1 for kw in _POSITIVE_KW if kw in text)
    neg_count  = sum(1 for kw in _NEGATIVE_KW if kw in text)

    trend = min(0.4 + high_count * 0.07 + _TYPE_BOOST.get(result_type, 0), 1.0)

    sentiment = 0.0
    if pos_count > neg_count:
        sentiment = min(0.3 + pos_count * 0.1, 1.0)
    elif neg_count > pos_count:
        sentiment = max(-0.3 - neg_count * 0.1, -1.0)

    importance = "high" if trend >= 0.7 else "medium" if trend >= 0.45 else "low"

    # Simple category detection
    cat = "news"
    if any(k in text for k in ["launch", "release", "gpt-", "model", "feature", "product"]):
        cat = "product_launch"
    elif any(k in text for k in ["partner", "deal", "acqui"]):
        cat = "partnership"
    elif any(k in text for k in ["hire", "join", "ceo", "executive", "leaves", "exit"]):
        cat = "hiring"
    elif any(k in text for k in ["research", "paper", "study", "benchmark"]):
        cat = "research"
    elif any(k in text for k in ["price", "pricing", "cost", "revenue", "billion", "million"]):
        cat = "pricing"
    elif any(k in text for k in ["ad", "campaign", "market"]):
        cat = "marketing"

    return {
        "summary":         title,
        "key_insights":    snippet[:300] if snippet else title,
        "why_it_matters":  "",
        "strategy_insight": "",
        "category":        cat,
        "trend_score":     round(trend, 2),
        "importance":      importance,
        "sentiment_score": round(sentiment, 2),
        "sentiment_label": "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral",
    }


# ── Selective LLM enrichment (max 3 calls per query) ─────────────────────────

def _enrich_top(items: list[dict], competitor: str, max_enrich: int = 3) -> int:
    """
    Call LLM for the top N highest-scoring items only.
    Mutates items in place. Returns number of tokens used.
    """
    top = sorted(
        [i for i in items if i.get("trend_score", 0) >= 0.6],
        key=lambda x: x["trend_score"],
        reverse=True,
    )[:max_enrich]

    total_tokens = 0
    for item in top:
        title   = item.get("title", "")
        snippet = item.get("snippet", "")[:400]
        rtype   = item.get("result_type", "news")

        prompt = (
            "Competitive intelligence analyst. Analyse this " + rtype + " about " + competitor + ".\n"
            "Title: " + title + "\n"
            "Snippet: " + snippet + "\n"
            "Return JSON only with keys: summary, key_insights, why_it_matters, strategy_insight"
        )

        result, tokens = call_llm(prompt, max_tokens=250, json_mode=True)
        total_tokens += tokens

        if result:
            item["summary"]          = result.get("summary", item["summary"])
            item["key_insights"]     = result.get("key_insights", item["key_insights"])
            item["why_it_matters"]   = result.get("why_it_matters", "")
            item["strategy_insight"] = result.get("strategy_insight", "")

        time.sleep(0.3)  # small pause between LLM calls to respect rate limits

    return total_tokens


# ── SerpAPI fetchers ──────────────────────────────────────────────────────────

def _call_serpapi(params: dict, api_key: str) -> Optional[dict]:
    try:
        r = requests.get(
            SERPAPI_URL,
            params={**params, "api_key": api_key, "hl": "en", "gl": "us"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        logger.warning(f"SerpAPI HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"SerpAPI request failed: {e}")
    return None


def _fetch_news(query: str, api_key: str) -> list[dict]:
    data = _call_serpapi({"engine": "google", "q": query, "tbm": "nws", "num": 10}, api_key)
    if not data:
        return []
    results = []
    for item in data.get("news_results", []):
        pub_date = None
        if item.get("date"):
            try:
                pub_date = datetime.strptime(item["date"], "%b %d, %Y")
            except Exception:
                pass
        results.append({
            "result_type": "news",
            "title":       item.get("title", ""),
            "url":         item.get("link", ""),
            "snippet":     item.get("snippet", ""),
            "source":      item.get("source", ""),
            "published_at": pub_date,
        })
    return results


def _fetch_organic(query: str, api_key: str) -> list[dict]:
    data = _call_serpapi({"engine": "google", "q": query, "num": 10}, api_key)
    if not data:
        return []
    results = []
    for item in data.get("organic_results", [])[:5]:
        results.append({
            "result_type": "organic",
            "title":       item.get("title", ""),
            "url":         item.get("link", ""),
            "snippet":     item.get("snippet", ""),
            "source":      item.get("displayed_link", ""),
            "published_at": None,
        })
    return results


def _fetch_ads(query: str, api_key: str) -> list[dict]:
    data = _call_serpapi({"engine": "google", "q": query, "num": 10}, api_key)
    if not data:
        return []
    results = []
    for item in data.get("ads", []):
        headline    = item.get("title", "")
        description = item.get("description", "")
        results.append({
            "result_type": "google_ads",
            "title":       headline,
            "url":         item.get("link", item.get("displayed_link", "")),
            "snippet":     description,
            "source":      item.get("displayed_link", ""),
            "published_at": None,
        })
    return results


def _fetch_trending(query: str, api_key: str) -> list[dict]:
    data = _call_serpapi({"engine": "google", "q": query}, api_key)
    if not data:
        return []
    results = []
    for item in data.get("related_searches", [])[:5]:
        kw = item.get("query", "")
        if kw and query.lower() not in kw.lower():
            results.append({
                "result_type": "trending",
                "title":       kw,
                "url":         "https://www.google.com/search?q=" + requests.utils.quote(kw),
                "snippet":     "Trending: " + kw,
                "source":      "google_related_searches",
                "published_at": None,
            })
    return results


# ── Persist ───────────────────────────────────────────────────────────────────

def _save_result(item: dict, competitor: str, db: Session, seen_urls: set) -> bool:
    url = item.get("url", "").strip()
    if not url:
        return False
    if url in seen_urls:
        return False
    seen_urls.add(url)
    if db.query(SerpResult).filter_by(url=url).first():
        return False

    db.add(SerpResult(
        competitor      = competitor,
        result_type     = item["result_type"],
        title           = item.get("title", "")[:500],
        url             = url[:1000],
        snippet         = item.get("snippet", "")[:2000],
        source          = item.get("source", "")[:200],
        summary         = item.get("summary", ""),
        key_insights    = item.get("key_insights", ""),
        why_it_matters  = item.get("why_it_matters", ""),
        category        = item.get("category", "other"),
        trend_score     = float(item.get("trend_score", 0.3)),
        importance      = item.get("importance", "medium"),
        sentiment_score = float(item.get("sentiment_score", 0.0)),
        sentiment_label = item.get("sentiment_label", "neutral"),
        published_at    = item.get("published_at"),
    ))
    try:
        db.flush()
        return True
    except IntegrityError:
        db.rollback()
        return False


# ── Main entrypoint ───────────────────────────────────────────────────────────

def run_serp_agent(competitor: dict, db: Session) -> dict:
    name     = competitor["name"]
    settings = get_settings()
    cfg      = get_config()

    serp_cfg = cfg.get("apis", {}).get("serpapi", {})
    if not serp_cfg.get("enabled", False):
        return {"serp_results_found": 0, "skipped": True, "competitor": name}

    api_key = settings.serpapi_key.strip()
    if not api_key:
        logger.warning(f"SerpAPI [{name}]: SERPAPI_KEY not set — skipping")
        return {"serp_results_found": 0, "skipped": True, "competitor": name}

    queries   = competitor.get("serp_queries", [name])[:serp_cfg.get("keywords_per_competitor", 5)]
    new_items = 0
    total_tok = 0
    seen_urls: set = set()

    with track_agent_run("serp_monitor", name, {"query_count": len(queries)}) as metrics:
        for query in queries:
            logger.info(f"SerpAPI [{name}]: querying '{query}'")

            # Fetch all result types
            all_results = (
                _fetch_news(query, api_key)
                + _fetch_organic(query, api_key)
                + _fetch_ads(query, api_key)
                + _fetch_trending(query, api_key)
            )

            # Step 1: score every result with rules (0 LLM calls)
            for item in all_results:
                if not item.get("title") or not item.get("url"):
                    continue
                scores = _score(item["title"], item.get("snippet", ""), item["result_type"])
                item.update(scores)

            # Step 2: LLM enrich top 3 high-signal items only (max 3 Groq calls per query)
            valid = [i for i in all_results if i.get("title") and i.get("url")]
            total_tok += _enrich_top(valid, name, max_enrich=3)

            # Step 3: save all to DB
            for item in valid:
                saved = _save_result(item, name, db, seen_urls)
                if saved:
                    new_items += 1
                    logger.info(
                        f"SerpAPI [{name}] {item['result_type']}: "
                        f"{item['title'][:60]} (trend={item.get('trend_score',0):.2f})"
                    )

            # Commit after each query
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.warning(f"SerpAPI [{name}]: commit failed for '{query}'")

            if len(queries) > 1:
                time.sleep(1.0)

        metrics["serp_results_found"] = new_items
        metrics["total_tokens_used"]  = total_tok
        metrics["items_found"]        = new_items

    logger.info(f"SerpAPI [{name}]: poll complete — {new_items} new results, {total_tok} tokens")
    return {"serp_results_found": new_items, "competitor": name}
