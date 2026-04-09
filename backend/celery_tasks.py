"""Celery task definitions for HireX Part 4."""

import asyncio
import logging
from uuid import UUID

from backend.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="backend.celery_tasks.score_submission_task",
    max_retries=3,
    default_retry_delay=10,
)
def score_submission_task(self, job_id: str) -> dict:
    """Celery task: run AI scoring for a single submission job."""
    from app.core.database import AsyncSessionLocal
    from backend.ai.scoring_pipeline import run_ai_scoring

    async def _run():
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await run_ai_scoring(db, UUID(job_id))

    try:
        _run_async(_run())
        return {"status": "completed", "job_id": job_id}
    except Exception as exc:
        logger.error(f"Celery task failed for job {job_id}: {exc}")
        raise self.retry(exc=exc)
