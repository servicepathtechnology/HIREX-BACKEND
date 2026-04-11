"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Central settings object — all config comes from .env."""

    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"

    # Store as plain str so pydantic-settings never tries to JSON-decode it.
    # Use the `allowed_origins_list` property everywhere in the app.
    allowed_origins: str = "*"

    @property
    def allowed_origins_list(self) -> List[str]:
        v = self.allowed_origins.strip()
        if v.startswith("["):
            try:
                return json.loads(v)
            except Exception:
                pass
        return [o.strip() for o in v.split(",") if o.strip()] or ["*"]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/hirex_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Firebase — use JSON env var in production, file path in local dev
    firebase_credentials_path: str = "./firebase-credentials.json"
    firebase_credentials_json: str = ""

    # AWS (Part 2)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = ""
    aws_cloudfront_url: str = ""
    aws_region: str = "us-east-1"

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

    # Part 1 — 1v1 Live Challenges
    judge0_api_key: str = ""
    challenge_room_base_url: str = "https://hirex-challenge-room.vercel.app"
    challenge_jwt_secret: str = "challenge-room-secret-change-in-prod"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
