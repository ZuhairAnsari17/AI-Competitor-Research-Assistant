"""
Database Migration — run ONCE before starting the server.
Adds every column that database.py defines but the old DB lacks.
Safe to run multiple times.

Usage:  python migrate_db.py
"""
import sqlite3, sys
from pathlib import Path

DB_PATH = Path("data/competitor.db")
if not DB_PATH.exists():
    print("No database found — will be created fresh on next server start.")
    sys.exit(0)

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()


def cols(table):
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}


def add(table, col, typ, default="NULL"):
    if col not in cols(table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ} DEFAULT {default}")
        print(f"  ✅  {table}.{col}")
    else:
        print(f"  —   {table}.{col} (exists)")


# ── blog_posts ────────────────────────────────────────────────────────────
print("blog_posts")
add("blog_posts", "key_insights",     "TEXT")
add("blog_posts", "why_it_matters",   "TEXT")
add("blog_posts", "strategy_insight", "TEXT")   # exact name in database.py
add("blog_posts", "trend_score",      "REAL",   "0.0")
add("blog_posts", "importance",       "TEXT",   "'medium'")
add("blog_posts", "source",           "TEXT",   "'rss'")

# ── youtube_videos ────────────────────────────────────────────────────────
print("youtube_videos")
add("youtube_videos", "summary",     "TEXT")
add("youtube_videos", "category",    "TEXT")
add("youtube_videos", "trend_score", "REAL", "0.0")

# ── reddit_mentions ───────────────────────────────────────────────────────
print("reddit_mentions")
add("reddit_mentions", "summary",     "TEXT")
add("reddit_mentions", "topic",       "TEXT")
add("reddit_mentions", "trend_score", "REAL", "0.0")

# ── meta_ads ──────────────────────────────────────────────────────────────
print("meta_ads")
add("meta_ads", "headline",     "TEXT")
add("meta_ads", "description",  "TEXT")
add("meta_ads", "cta",          "TEXT")
add("meta_ads", "landing_url",  "TEXT")
add("meta_ads", "ad_type",      "TEXT")
add("meta_ads", "ad_summary",   "TEXT")
add("meta_ads", "source",       "TEXT", "'meta_api'")

# ── agent_runs — no new columns needed in this version ───────────────────

# ── new tables ────────────────────────────────────────────────────────────
print("serp_results")
cur.execute("""CREATE TABLE IF NOT EXISTS serp_results (
    id              INTEGER PRIMARY KEY,
    competitor      TEXT,
    result_type     TEXT,
    title           TEXT,
    url             TEXT UNIQUE,
    snippet         TEXT,
    source          TEXT,
    summary         TEXT,
    key_insights    TEXT,
    why_it_matters  TEXT,
    category        TEXT,
    trend_score     REAL    DEFAULT 0.0,
    importance      TEXT    DEFAULT 'medium',
    sentiment_score REAL    DEFAULT 0.0,
    sentiment_label TEXT    DEFAULT 'neutral',
    published_at    DATETIME,
    detected_at     DATETIME,
    alerted         INTEGER DEFAULT 0
)""")
print("  ✅  serp_results")

cur.execute("""CREATE TABLE IF NOT EXISTS eval_results (
    id           INTEGER PRIMARY KEY,
    evaluated_at DATETIME,
    metric_name  TEXT,
    score        REAL,
    details      TEXT
)""")
print("  ✅  eval_results")

conn.commit()
conn.close()
print("\n✅  Migration complete — restart the server.")
