"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import json


class Settings(BaseSettings):
    """Central settings object — all config comes from .env."""

    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    allowed_origins: List[str] = ["*"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Plain string like "*" or comma-separated
            return [o.strip() for o in v.split(",") if o.strip()]
        return ["*"]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/hirex_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Firebase — use JSON env var in production, file path in local dev
    firebase_credentials_path: str = "./firebase-credentials.json"
    firebase_credentials_json: str = ""  # JSON string, takes priority over path

    # AWS (Part 2)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = ""
    aws_cloudfront_url: str = ""

    # Razorpay (Part 3)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # OpenAI (Part 4)
    openai_api_key: str = ""

    # Celery (Part 4)
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Part 5
    sentry_dsn: str = ""
    mixpanel_token: str = ""
    branch_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
