from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import get_config

Path("data").mkdir(exist_ok=True)

Base          = declarative_base()
engine        = create_engine(get_config()["database"]["url"], connect_args={"check_same_thread": False})
SessionLocal  = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class BlogPost(Base):
    __tablename__ = "blog_posts"
    id               = Column(Integer, primary_key=True)
    competitor       = Column(String(100), index=True)
    title            = Column(String(500))
    url              = Column(String(1000), unique=True)
    published_at     = Column(DateTime)
    summary          = Column(Text)
    key_insights     = Column(Text)
    why_it_matters   = Column(Text)
    strategy_insight = Column(Text)
    sentiment_score  = Column(Float)
    sentiment_label  = Column(String(20))
    keywords         = Column(JSON)
    trend_score      = Column(Float, default=0.0)
    importance       = Column(String(10), default="medium")
    source           = Column(String(20), default="rss")
    detected_at      = Column(DateTime, default=datetime.utcnow)
    alerted          = Column(Boolean, default=False)


class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"
    id           = Column(Integer, primary_key=True)
    competitor   = Column(String(100), index=True)
    video_id     = Column(String(50), unique=True)
    title        = Column(String(500))
    url          = Column(String(200))
    views        = Column(Integer, default=0)
    likes        = Column(Integer, default=0)
    comments     = Column(Integer, default=0)
    summary      = Column(Text)
    category     = Column(String(50))
    trend_score  = Column(Float, default=0.0)
    published_at = Column(DateTime)
    detected_at  = Column(DateTime, default=datetime.utcnow)
    alerted      = Column(Boolean, default=False)


class RedditMention(Base):
    __tablename__ = "reddit_mentions"
    id              = Column(Integer, primary_key=True)
    competitor      = Column(String(100), index=True)
    post_id         = Column(String(50), unique=True)
    title           = Column(String(500))
    url             = Column(String(500))
    subreddit       = Column(String(100))
    score           = Column(Integer, default=0)
    num_comments    = Column(Integer, default=0)
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))
    summary         = Column(Text)
    topic           = Column(String(50))
    trend_score     = Column(Float, default=0.0)
    created_at      = Column(DateTime)
    detected_at     = Column(DateTime, default=datetime.utcnow)


class MetaAd(Base):
    __tablename__ = "meta_ads"
    id                  = Column(Integer, primary_key=True)
    competitor          = Column(String(100), index=True)
    ad_id               = Column(String(100), unique=True)
    ad_creative_body    = Column(Text)
    headline            = Column(String(500))
    description         = Column(Text)
    cta                 = Column(String(100))
    landing_url         = Column(String(1000))
    page_name           = Column(String(200))
    ad_type             = Column(String(50))
    ad_summary          = Column(Text)
    delivery_start_time = Column(DateTime)
    platforms           = Column(JSON)
    source              = Column(String(20), default="meta_api")
    detected_at         = Column(DateTime, default=datetime.utcnow)
    alerted             = Column(Boolean, default=False)


class SerpResult(Base):
    __tablename__ = "serp_results"
    id              = Column(Integer, primary_key=True)
    competitor      = Column(String(100), index=True)
    result_type     = Column(String(30), index=True)
    title           = Column(String(500))
    url             = Column(String(1000), unique=True)
    snippet         = Column(Text)
    source          = Column(String(200))
    summary         = Column(Text)
    key_insights    = Column(Text)
    why_it_matters  = Column(Text)
    category        = Column(String(50))
    trend_score     = Column(Float, default=0.0)
    importance      = Column(String(10), default="medium")
    sentiment_score = Column(Float)
    sentiment_label = Column(String(20))
    published_at    = Column(DateTime)
    detected_at     = Column(DateTime, default=datetime.utcnow)
    alerted         = Column(Boolean, default=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id            = Column(Integer, primary_key=True)
    run_at        = Column(DateTime, default=datetime.utcnow)
    agent_name    = Column(String(100))
    competitor    = Column(String(100))
    status        = Column(String(20))
    items_found   = Column(Integer, default=0)
    latency_ms    = Column(Float)
    tokens_used   = Column(Integer, default=0)
    error_msg     = Column(Text)
    mlflow_run_id = Column(String(100))


class EvalResult(Base):
    __tablename__ = "eval_results"
    id           = Column(Integer, primary_key=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    metric_name  = Column(String(100))
    score        = Column(Float)
    details      = Column(JSON)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
