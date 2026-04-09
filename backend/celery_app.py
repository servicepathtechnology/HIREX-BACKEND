"""Celery application configuration for HireX Part 4."""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "hirex",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.celery_tasks.score_submission_task": {"queue": "ai_scoring"},
    },
)
