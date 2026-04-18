import yaml
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    groq_api_key:         str = Field(default="", env="GROQ_API_KEY")
    openai_api_key:       str = Field(default="", env="OPENAI_API_KEY")
    youtube_api_key:      str = Field(default="", env="YOUTUBE_API_KEY")
    meta_access_token:    str = Field(default="", env="META_ACCESS_TOKEN")
    reddit_client_id:     str = Field(default="", env="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", env="REDDIT_CLIENT_SECRET")
    reddit_user_agent:    str = Field(default="CompetitorIntelBot/1.0", env="REDDIT_USER_AGENT")
    serpapi_key:          str = Field(default="", env="SERPAPI_KEY")
    dagshub_username:     str = Field(default="", env="DAGSHUB_USERNAME")
    dagshub_repo_name:    str = Field(default="", env="DAGSHUB_REPO_NAME")
    dagshub_token:        str = Field(default="", env="DAGSHUB_TOKEN")
    mlflow_experiment:    str = Field(default="competitor-intelligence", env="MLFLOW_EXPERIMENT_NAME")
    alert_email_from:     str = Field(default="", env="ALERT_EMAIL_FROM")
    alert_email_to:       str = Field(default="", env="ALERT_EMAIL_TO")
    smtp_password:        str = Field(default="", env="SMTP_PASSWORD")
    slack_webhook_url:    str = Field(default="", env="SLACK_WEBHOOK_URL")
    app_env:              str = Field(default="development", env="APP_ENV")
    secret_key:           str = Field(default="dev-secret-change-me", env="SECRET_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


@lru_cache()
def get_config() -> dict:
    path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def invalidate_config_cache():
    get_config.cache_clear()
    get_settings.cache_clear()


def get_competitors() -> list:
    return get_config().get("competitors", [])


def get_active_competitor_names() -> set:
    return {c["name"] for c in get_competitors()}


def get_alert_config() -> dict:
    return get_config().get("alerts", {})
