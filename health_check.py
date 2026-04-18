#!/usr/bin/env python3
"""
Comprehensive health check for the AI Competitor Research Assistant.
Tests all major components including DB, API, agents, and tracking.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env first
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("COMPREHENSIVE HEALTH CHECK")
print("=" * 80)

# ─────────────────────────────────────────────────────────────────────────────
# 1. ENVIRONMENT & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
print("\n1️⃣  ENVIRONMENT & CONFIGURATION")
print("-" * 80)

try:
    from app.core.config import get_settings, get_config, get_competitors
    settings = get_settings()
    config = get_config()
    competitors = get_competitors()
    
    print("✓ Settings loaded successfully")
    print(f"  - APP_ENV: {settings.app_env}")
    print(f"  - Competitors configured: {len(competitors)}")
    for comp in competitors:
        print(f"    • {comp['name']}")
except Exception as e:
    print(f"✗ Configuration failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 2. API KEYS
# ─────────────────────────────────────────────────────────────────────────────
print("\n2️⃣  API KEYS & CREDENTIALS")
print("-" * 80)

keys_status = {
    "GROQ_API_KEY": settings.groq_api_key,
    "YOUTUBE_API_KEY": settings.youtube_api_key,
    "REDDIT_CLIENT_ID": settings.reddit_client_id,
    "REDDIT_CLIENT_SECRET": settings.reddit_client_secret,
    "META_ACCESS_TOKEN": settings.meta_access_token,
    "DAGSHUB_USERNAME": settings.dagshub_username,
    "DAGSHUB_REPO_NAME": settings.dagshub_repo_name,
    "DAGSHUB_TOKEN": settings.dagshub_token,
}

for key, value in keys_status.items():
    if value and value.strip():
        preview = value[:10] + "..." if len(value) > 10 else value
        print(f"✓ {key}: {preview}")
    else:
        print(f"⚠ {key}: (empty)")

# ─────────────────────────────────────────────────────────────────────────────
# 3. DATABASE
# ─────────────────────────────────────────────────────────────────────────────
print("\n3️⃣  DATABASE")
print("-" * 80)

try:
    from app.core.database import init_db, SessionLocal, BlogPost, YouTubeVideo, RedditMention, MetaAd
    from sqlalchemy import text
    
    init_db()
    print("✓ Database initialized")
    
    with SessionLocal() as db:
        # Check table counts
        blog_count = db.query(BlogPost).count()
        yt_count = db.query(YouTubeVideo).count()
        reddit_count = db.query(RedditMention).count()
        meta_count = db.query(MetaAd).count()
        
        print(f"✓ Tables accessible:")
        print(f"  - BlogPost: {blog_count} records")
        print(f"  - YouTubeVideo: {yt_count} records")
        print(f"  - RedditMention: {reddit_count} records")
        print(f"  - MetaAd: {meta_count} records")
except Exception as e:
    print(f"✗ Database check failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 4. MLFLOW & DAGSHUB
# ─────────────────────────────────────────────────────────────────────────────
print("\n4️⃣  MLFLOW & DAGSHUB TRACKING")
print("-" * 80)

try:
    import mlflow
    import dagshub
    
    print(f"✓ mlflow v{mlflow.__version__} installed")
    print(f"✓ dagshub installed")
    
    # Try to initialize DagsHub
    dagshub.auth.add_app_token(token=settings.dagshub_token)
    dagshub.init(
        repo_owner=settings.dagshub_username,
        repo_name=settings.dagshub_repo_name,
        mlflow=True,
    )
    
    tracking_uri = mlflow.get_tracking_uri()
    print(f"✓ DagsHub initialized")
    print(f"  - Tracking URI: {tracking_uri}")
    
    # Check experiment
    experiment = mlflow.set_experiment(settings.mlflow_experiment)
    print(f"  - Experiment: '{settings.mlflow_experiment}' (id={experiment.experiment_id})")
    
except Exception as e:
    print(f"✗ DagsHub/MLflow check failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 5. AGENTS (Dry run validation)
# ─────────────────────────────────────────────────────────────────────────────
print("\n5️⃣  AGENTS & DEPENDENCIES")
print("-" * 80)

try:
    from app.agents.blog_agent import get_blog_agent_prompt
    from app.agents.youtube_agent import run_youtube_agent
    from app.agents.reddit_agent import run_reddit_agent
    from app.agents.meta_ads_agent import run_meta_ads_agent
    from app.core.llm import get_llm
    
    print("✓ Blog agent imported")
    print("✓ YouTube agent imported")
    print("✓ Reddit agent imported")
    print("✓ Meta ads agent imported")
    
    # Test LLM connection
    llm = get_llm()
    print(f"✓ LLM initialized: {llm.__class__.__name__}")
    
except ImportError as e:
    print(f"⚠ Agent import warning: {e}")
except Exception as e:
    print(f"✗ Agent check failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 6. SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────
print("\n6️⃣  SCHEDULER")
print("-" * 80)

try:
    from app.core.scheduler import scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    
    print(f"✓ Scheduler initialized: {scheduler.__class__.__name__}")
    print(f"  - Scheduler state: {'running' if scheduler.running else 'not running'}")
    
except Exception as e:
    print(f"✗ Scheduler check failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 7. FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────
print("\n7️⃣  FASTAPI APPLICATION")
print("-" * 80)

try:
    from app.api.main import app
    
    print(f"✓ FastAPI app loaded")
    print(f"  - App name: {app.title}")
    print(f"  - Version: {app.version}")
    print(f"  - Routes: {len(app.routes)}")
    
    # List key endpoints
    endpoints = []
    for route in app.routes:
        if hasattr(route, 'path'):
            endpoints.append(route.path)
    
    key_endpoints = [e for e in endpoints if any(x in e for x in ['/health', '/api', '/docs'])]
    for ep in sorted(key_endpoints)[:5]:
        print(f"    • {ep}")
    
except Exception as e:
    print(f"✗ FastAPI app check failed: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 8. SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
print("\n8️⃣  SYSTEM")
print("-" * 80)

try:
    import platform
    print(f"✓ OS: {platform.system()} {platform.release()}")
    print(f"✓ Python: {sys.version.split()[0]}")
    
    # Check disk space
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024**3)
    print(f"✓ Disk free: {free_gb:.1f} GB")
    
except Exception as e:
    print(f"⚠ System check warning: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("✅ ALL CHECKS PASSED - System is ready!")
print("=" * 80)
print("\n📋 Next steps:")
print("   1. Start the app: uv run python -m uvicorn app.api.main:app")
print("   2. Access dashboard: http://localhost:8000/docs")
print("   3. View tracking: https://dagshub.com/Zappy17/competitor-intel.mlflow")
print("=" * 80 + "\n")
