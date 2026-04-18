import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Patch scheduler so it doesn't run during tests
import unittest.mock as mock
with mock.patch("app.core.scheduler.start_scheduler"), \
     mock.patch("app.core.scheduler.run_all_agents"), \
     mock.patch("app.core.tracking.setup_mlflow"):
    from app.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_competitors_endpoint():
    r = client.get("/api/competitors")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_summary_endpoint():
    r = client.get("/api/summary")
    assert r.status_code == 200
    data = r.json()
    assert "competitors_tracked" in data
    assert "blog_posts_7d" in data


def test_blog_posts_endpoint():
    r = client.get("/api/blog-posts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_youtube_endpoint():
    r = client.get("/api/youtube")
    assert r.status_code == 200


def test_reddit_endpoint():
    r = client.get("/api/reddit")
    assert r.status_code == 200


def test_runs_endpoint():
    r = client.get("/api/runs")
    assert r.status_code == 200


def test_evaluations_endpoint():
    r = client.get("/api/evaluations")
    assert r.status_code == 200


def test_sentiment_endpoint():
    r = client.get("/api/sentiment")
    assert r.status_code == 200
