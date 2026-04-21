"""
Basic API smoke tests — run with: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
import os

# Set dummy env vars before importing the app
os.environ.setdefault("GROQ_API_KEY",        "test_key")
os.environ.setdefault("YOUTUBE_API_KEY",     "test_key")
os.environ.setdefault("DAGSHUB_USERNAME",    "test")
os.environ.setdefault("DAGSHUB_REPO_NAME",   "test")
os.environ.setdefault("DAGSHUB_TOKEN",       "test")
os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", "test")


@pytest.fixture(scope="module")
def client():
    from app.api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert "version" in data


def test_summary(client):
    r = client.get("/api/summary")
    assert r.status_code == 200
    data = r.json()
    assert "blog_posts_7d"      in data
    assert "youtube_videos_7d"  in data
    assert "reddit_mentions_7d" in data
    assert "competitors_tracked" in data


def test_competitors(client):
    r = client.get("/api/competitors")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_blog_posts(client):
    r = client.get("/api/blog-posts?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_youtube(client):
    r = client.get("/api/youtube?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_reddit(client):
    r = client.get("/api/reddit?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_serp(client):
    r = client.get("/api/serp?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_runs(client):
    r = client.get("/api/runs?limit=10")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sentiment(client):
    r = client.get("/api/sentiment")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_reload_config(client):
    r = client.post("/api/reload-config")
    assert r.status_code == 200
    assert "competitors" in r.json()


def test_no_ads_endpoint(client):
    """Meta ads endpoint should be gone."""
    r = client.get("/api/ads")
    assert r.status_code == 404
