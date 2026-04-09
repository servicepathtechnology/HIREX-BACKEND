"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Central settings object — all config comes from .env."""

    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    allowed_origins: List[str] = ["*"]

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

    def model_post_init(self, __context) -> None:
        # Handle ALLOWED_ORIGINS as JSON array string from .env
        if isinstance(self.allowed_origins, list) and len(self.allowed_origins) == 1:
            raw = self.allowed_origins[0]
            if raw.startswith('['):
                try:
                    object.__setattr__(self, 'allowed_origins', json.loads(raw))
                except Exception:
                    pass


settings = Settings()
