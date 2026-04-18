"""
Meta Ads Agent — scrapes Facebook Ad Library for competitor ads.

Strategies (tried in order):
  1. Official Meta Graph API  — if META_ACCESS_TOKEN set (most reliable, returns full creative)
  2. GraphQL (no token)       — FB's internal endpoint
  3. HTML regex fallback      — last resort

LLM extracts: headline, description, CTA, ad_type, ad_summary from ad body.
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import MetaAd
from app.core.llm import call_llm
from app.core.tracking import track_agent_run

logger = logging.getLogger(__name__)

AD_LIB_URL    = "https://www.facebook.com/ads/library/"
GQL_URL       = "https://www.facebook.com/api/graphql/"
GRAPH_API_URL = "https://graph.facebook.com/v19.0/ads_archive"
DOC_KEYWORD   = "8047925941970161"
DOC_PAGE      = "6546827748689488"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── LLM creative extraction ───────────────────────────────────────────────────

def _extract_ad_creative(body: str, page_name: str, competitor: str) -> tuple[dict, int]:
    """Use LLM to extract structured fields from raw ad body text."""
    if not body or len(body.strip()) < 10:
        return {}, 0

    prompt = f"""You are an ad analyst. Extract structured data from this Facebook ad creative.

Ad body text: {body[:800]}
Page: {page_name}
Advertiser: {competitor}

Return JSON only:
{{
  "headline": "the main headline or product name (max 100 chars)",
  "description": "the main ad description or value proposition",
  "cta": "call-to-action text e.g. 'Sign Up', 'Learn More', 'Try Free'",
  "ad_type": "product_launch|brand_awareness|promotion|recruitment|feature|retargeting|other",
  "ad_summary": "one sentence: what this ad is promoting and its key message",
  "key_message": "5-10 word core message"
}}"""
    return call_llm(prompt, max_tokens=300, json_mode=True)


# ── Strategy 1: Official Meta Graph API ───────────────────────────────────────

def _fetch_official_api(
    query: str, access_token: str, country: str, page_id: str = "",
) -> list[dict]:
    params = {
        "access_token":         access_token,
        "ad_reached_countries": json.dumps([country]),
        "ad_active_status":     "ACTIVE",
        "ad_type":              "ALL",
        "fields": (
            "id,ad_creative_bodies,ad_creative_link_captions,"
            "ad_creative_link_titles,ad_creative_link_descriptions,"
            "page_name,ad_delivery_start_time,publisher_platforms"
        ),
        "limit": 30,
    }
    if page_id:
        params["search_page_ids"] = page_id
    else:
        params["search_terms"] = query

    try:
        r = requests.get(GRAPH_API_URL, params=params, timeout=20)
        if r.status_code == 200:
            items = r.json().get("data", [])
            logger.info(f"[Official API] {len(items)} ads for '{query or page_id}'")
            ads = []
            for item in items:
                bodies      = item.get("ad_creative_bodies") or []
                captions    = item.get("ad_creative_link_captions") or []
                titles      = item.get("ad_creative_link_titles") or []
                descriptions = item.get("ad_creative_link_descriptions") or []

                # Build richest possible body
                body_parts = list(filter(None, bodies + captions + titles + descriptions))
                body = " | ".join(body_parts)[:2000]

                # Try to get headline from titles
                headline = (titles[0] if titles else (bodies[0] if bodies else ""))[:500]

                ads.append({
                    "ad_id":      f"api_{item.get('id','')}",
                    "page_name":  item.get("page_name", query),
                    "body":       body,
                    "headline":   headline,
                    "start_time": item.get("ad_delivery_start_time"),
                    "platforms":  item.get("publisher_platforms") or ["facebook"],
                    "source":     "official_api",
                })
            return ads
        err = r.json().get("error", {})
        logger.warning(f"[Official API] HTTP {r.status_code}: {err.get('message','')}")
    except Exception as e:
        logger.error(f"[Official API] failed: {e}")
    return []


# ── Strategy 2: GraphQL (no token) ────────────────────────────────────────────

def _get_tokens() -> tuple[str, Optional[str]]:
    lsd, dtsg = "AVqbxe3J_RA", None
    try:
        r    = requests.get(AD_LIB_URL, headers={**HEADERS, "Accept": "text/html,*/*"}, timeout=15)
        html = r.text
        for pat in [r'"LSD",[^,]+,{"token":"([^"]+)"', r'"lsd":"([^"]+)"']:
            m = re.search(pat, html)
            if m:
                lsd = m.group(1)
                break
        for pat in [r'"DTSGInitialData"[^{]+{"token":"([^"]+)"', r'"fb_dtsg":{"value":"([^"]+)"']:
            m = re.search(pat, html)
            if m:
                dtsg = m.group(1)
                break
    except Exception:
        pass
    return lsd, dtsg


def _gql_post(payload: dict, lsd: str) -> dict:
    try:
        r = requests.post(
            GQL_URL,
            headers={
                **HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin":       "https://www.facebook.com",
                "Referer":      AD_LIB_URL,
                "X-FB-LSD":     lsd,
            },
            data=payload,
            timeout=20,
        )
        text = r.text
        for prefix in ("for (;;);", "for(;;);"):
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        return json.loads(text)
    except Exception as e:
        logger.warning(f"[GQL] post failed: {e}")
        return {}


def _parse_gql_nodes(data: dict) -> list[dict]:
    ads = []
    edges = (
        data.get("data", {}).get("ad_library_main", {})
        .get("search_results_connection", {}).get("edges", [])
    )
    if not edges:
        edges = (
            data.get("data", {}).get("ad_library_page", {})
            .get("ad_library_page_ads", {}).get("edges", [])
        )

    for edge in edges:
        node  = edge.get("node", {})
        ad_id = (
            node.get("ad_archive_id")
            or node.get("adArchiveID")
            or node.get("id", "")
        )
        if not ad_id:
            continue

        body = ""
        for src in [node] + (node.get("collated_results") or [])[:1]:
            snap     = src.get("snapshot") or {}
            body_raw = snap.get("body") or {}
            body     = body_raw.get("text", "") if isinstance(body_raw, dict) else str(body_raw)
            if body:
                break

        start_ts  = node.get("start_date") or node.get("ad_delivery_start_time")
        start_iso = None
        if start_ts:
            try:
                start_iso = datetime.utcfromtimestamp(int(start_ts)).isoformat()
            except (ValueError, TypeError):
                start_iso = str(start_ts)

        platforms = node.get("publisher_platform") or ["facebook"]
        ads.append({
            "ad_id":      f"gql_{ad_id}",
            "page_name":  node.get("page_name") or node.get("pageName") or "",
            "body":       body[:2000],
            "headline":   "",
            "start_time": start_iso,
            "platforms":  [p.lower() for p in platforms] if platforms else ["facebook"],
            "source":     "graphql",
        })

    return ads


def _fetch_gql_keyword(query: str, country: str) -> list[dict]:
    lsd, dtsg = _get_tokens()
    payload = {
        "lsd": lsd,
        "fb_api_req_friendly_name": "AdLibrarySearchPaginatedAdsQuery",
        "variables": json.dumps({
            "activeStatus": "active", "adType": "ALL", "bylines": [],
            "countries": [country], "cursor": None, "first": 30,
            "isTargetedCountry": False, "mediaType": "all",
            "publisherPlatforms": [], "queryString": query,
            "searchType": "keyword_unordered",
            "sessionID": hashlib.md5(f"{query}{time.time()}".encode()).hexdigest(),
            "sortData": {"mode": "total_impressions", "direction": "desc"},
            "verboseData": False,
        }),
        "doc_id": DOC_KEYWORD, "__user": "0", "__a": "1",
        "server_timestamps": "true",
    }
    if dtsg:
        payload["fb_dtsg"] = dtsg
    return _parse_gql_nodes(_gql_post(payload, lsd))


def _fetch_gql_page_id(page_id: str, country: str) -> list[dict]:
    lsd, dtsg = _get_tokens()
    payload = {
        "lsd": lsd,
        "fb_api_req_friendly_name": "AdLibraryPagedAdsByPageIDQuery",
        "variables": json.dumps({
            "pageID": page_id, "adType": "ALL", "countries": [country],
            "activeStatus": "active", "first": 30, "cursor": None,
            "mediaType": "all",
            "sortData": {"mode": "relevancy_monthly_grouped", "direction": "desc"},
            "sessionID": hashlib.md5(f"{page_id}{time.time()}".encode()).hexdigest(),
        }),
        "doc_id": DOC_PAGE, "__user": "0", "__a": "1",
        "server_timestamps": "true",
    }
    if dtsg:
        payload["fb_dtsg"] = dtsg
    return _parse_gql_nodes(_gql_post(payload, lsd))


# ── Strategy 3: HTML regex fallback ───────────────────────────────────────────

def _fetch_html_fallback(query: str, country: str) -> list[dict]:
    url = (
        f"{AD_LIB_URL}?active_status=active&ad_type=all"
        f"&country={country}&is_targeted_country=false&media_type=all"
        f"&q={requests.utils.quote(query)}&search_type=keyword_unordered"
    )
    try:
        r    = requests.get(url, headers={**HEADERS, "Accept": "text/html,*/*"}, timeout=20)
        html = r.text
        ads  = []

        ad_ids  = re.findall(r'"adArchiveID"\s*:\s*"(\d+)"', html)
        bodies  = re.findall(r'"body"\s*:\s*\{\s*"text"\s*:\s*"([^"]{10,500})"', html)
        pages_  = re.findall(r'"pageName"\s*:\s*"([^"]+)"', html)
        starts  = re.findall(r'"startDate"\s*:\s*(\d+)', html)

        if not ad_ids:
            ad_ids  = re.findall(r'"ad_archive_id"\s*:\s*"(\d+)"', html)
            bodies  = re.findall(r'"ad_creative_body"\s*:\s*"([^"]{10,300})"', html)
            pages_  = re.findall(r'"page_name"\s*:\s*"([^"]+)"', html)
            starts  = re.findall(r'"ad_delivery_start_time"\s*:\s*"([^"]+)"', html)

        for i, ad_id in enumerate(ad_ids[:30]):
            start_val = starts[i] if i < len(starts) else None
            start_iso = None
            if start_val:
                try:
                    start_iso = datetime.utcfromtimestamp(int(start_val)).isoformat()
                except (ValueError, TypeError):
                    start_iso = str(start_val)

            body = bodies[i] if i < len(bodies) else ""
            # Unescape common HTML entities
            body = body.replace("\\n", "\n").replace('\\"', '"').replace("\\u0026", "&")

            ads.append({
                "ad_id":      f"html_{ad_id}",
                "page_name":  pages_[i] if i < len(pages_) else query,
                "body":       body,
                "headline":   "",
                "start_time": start_iso,
                "platforms":  ["facebook"],
                "source":     "html_fallback",
            })

        logger.info(f"[HTML fallback] {len(ads)} ads for '{query}'")
        return ads
    except Exception as e:
        logger.error(f"[HTML fallback] failed: {e}")
        return []


# ── Persist ────────────────────────────────────────────────────────────────────

def _save(ads: list[dict], name: str, db: Session, seen_ad_ids: set[str]) -> int:
    saved = 0
    for ad in ads:
        ad_id = ad.get("ad_id", "")
        if not ad_id or ad_id in seen_ad_ids:
            continue
        if db.query(MetaAd).filter_by(ad_id=ad_id).first():
            seen_ad_ids.add(ad_id)
            continue

        start_dt = None
        if ad.get("start_time"):
            try:
                start_dt = datetime.fromisoformat(
                    str(ad["start_time"]).replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                pass

        platforms = ad.get("platforms") or ["facebook"]
        if isinstance(platforms, str):
            platforms = [platforms]

        analysis = ad.get("_analysis", {})

        db.add(MetaAd(
            competitor          = name,
            ad_id               = ad_id,
            ad_creative_body    = ad.get("body", "")[:2000],
            headline            = (analysis.get("headline") or ad.get("headline", ""))[:500],
            description         = analysis.get("description", "")[:2000],
            cta                 = analysis.get("cta", "")[:100],
            page_name           = ad.get("page_name", name),
            ad_type             = analysis.get("ad_type", ""),
            ad_summary          = analysis.get("ad_summary", ""),
            delivery_start_time = start_dt,
            platforms           = platforms,
            source              = ad.get("source", "unknown"),
        ))
        seen_ad_ids.add(ad_id)
        saved += 1
        logger.info(
            f"Meta Ads [{name}] saved {ad_id} "
            f"(src={ad.get('source','?')}, "
            f"type={analysis.get('ad_type','?')}, "
            f"headline={analysis.get('headline','')[:40]})"
        )
    return saved


# ── Main entrypoint ────────────────────────────────────────────────────────────

def run_meta_ads_agent(competitor: dict, db: Session) -> dict:
    name         = competitor["name"]
    settings     = get_settings()
    queries      = competitor.get("meta_ad_queries", [name])
    country      = competitor.get("meta_ad_country", "IN")
    page_id      = competitor.get("meta_fb_page_id", "").strip()
    access_token = settings.meta_access_token.strip()
    new_ads      = 0
    total_tok    = 0

    with track_agent_run(
        "meta_ads_monitor", name,
        {"queries": len(queries), "country": country,
         "page_id": page_id or "none",
         "mode": "official_api" if access_token else "scraper"},
    ) as metrics:

        seen_ad_ids: set[str] = set()

        def _enrich_and_collect(ads: list[dict]):
            nonlocal total_tok
            for ad in ads:
                body = ad.get("body", "").strip()
                if body and len(body) >= 10:
                    analysis, tok = _extract_ad_creative(body, ad.get("page_name", ""), name)
                    total_tok += tok
                    ad["_analysis"] = analysis
                else:
                    ad["_analysis"] = {}

        # ── Page-ID search ─────────────────────────────────────────────────
        if page_id:
            ads: list[dict] = []
            if access_token:
                ads = _fetch_official_api("", access_token, country, page_id=page_id)
            if not ads:
                ads = _fetch_gql_page_id(page_id, country)
            _enrich_and_collect(ads)
            new_ads += _save(ads, name, db, seen_ad_ids)

        # ── Keyword search ─────────────────────────────────────────────────
        for query in queries:
            ads = []
            if access_token:
                ads = _fetch_official_api(query, access_token, country)
            if not ads:
                ads = _fetch_gql_keyword(query, country)
            if not ads:
                ads = _fetch_html_fallback(query, country)

            _enrich_and_collect(ads)
            new_ads += _save(ads, name, db, seen_ad_ids)

            if len(queries) > 1:
                time.sleep(1.0)

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        metrics["ads_found"]          = new_ads
        metrics["total_tokens_used"]  = total_tok
        metrics["items_found"]        = new_ads

    return {"new_ads": new_ads, "competitor": name}
