"""AI scoring pipeline — called by Celery worker."""

import json
import logging
from datetime import datetime
from uuid import UUID

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.part4 import AIScoringJob
from app.models.task import Submission, Task

from .prompts.scoring_prompt import SYSTEM_PROMPT, build_scoring_prompt

logger = logging.getLogger(__name__)

_openai_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def run_ai_scoring(db: AsyncSession, job_id: UUID) -> None:
    """Core scoring logic — runs inside Celery worker via sync wrapper."""
    # Fetch job
    job_result = await db.execute(select(AIScoringJob).where(AIScoringJob.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        logger.error(f"AI scoring job {job_id} not found")
        return

    # Fetch submission and task
    sub_result = await db.execute(select(Submission).where(Submission.id == job.submission_id))
    submission = sub_result.scalar_one_or_none()

    task_result = await db.execute(select(Task).where(Task.id == job.task_id))
    task = task_result.scalar_one_or_none()

    if not submission or not task:
        job.status = "failed"
        job.error_message = "Submission or task not found"
        await db.flush()
        return

    job.status = "processing"
    await db.flush()

    # Build prompt
    criteria = task.evaluation_criteria if isinstance(task.evaluation_criteria, list) else []
    task_dict = {
        "title": task.title,
        "domain": task.domain,
        "difficulty": task.difficulty,
        "problem_statement": task.problem_statement,
    }
    sub_dict = {
        "text_content": submission.text_content,
        "code_content": submission.code_content,
        "code_language": submission.code_language,
        "link_url": submission.link_url,
        "file_urls": submission.file_urls,
        "notes": submission.notes,
    }

    user_prompt = build_scoring_prompt(task_dict, sub_dict, criteria)

    # Call OpenAI with retry logic
    ai_response = await _call_openai_with_retry(user_prompt, job)
    if ai_response is None:
        await db.flush()
        return

    # Parse response
    try:
        parsed = json.loads(ai_response)
    except json.JSONDecodeError:
        # Retry with temperature=0
        ai_response2 = await _call_openai_with_retry(user_prompt, job, temperature=0.0, force=True)
        if ai_response2 is None:
            await db.flush()
            return
        try:
            parsed = json.loads(ai_response2)
        except json.JSONDecodeError:
            job.status = "failed"
            job.error_message = "OpenAI returned malformed JSON after retry"
            await db.flush()
            return

    # Store results
    job.ai_scores = {
        c["criterion_name"]: {
            "score": c["score"],
            "reasoning": c["reasoning"],
            "suggestion": c["improvement_suggestion"],
        }
        for c in parsed.get("criteria_scores", [])
    }
    job.ai_total_score = parsed.get("total_score")
    job.ai_summary = parsed.get("executive_summary")
    job.ai_flags = {
        "plagiarism_suspected": parsed.get("plagiarism_suspected", False),
        "ai_generated_suspected": parsed.get("ai_generated_suspected", False),
        "reason": parsed.get("flags_reasoning", ""),
    }
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    await db.flush()

    logger.info(f"AI scoring job {job_id} completed. Total score: {job.ai_total_score}")

    # Notify recruiter that AI scoring is complete
    try:
        from app.services.notification_service import create_notification
        from backend.notifications.fcm_service import push_ai_scoring_complete
        await create_notification(
            db=db,
            user_id=task.recruiter_id,
            notif_type="ai_scoring_complete",
            title="AI Review Ready",
            body=f"AI scoring complete for a submission on '{task.title}' — ready for review.",
            data={"task_id": str(task.id), "submission_id": str(submission.id), "type": "ai_scoring_complete"},
        )
        await push_ai_scoring_complete(db, task.recruiter_id, task.title, task.id, 1)
    except Exception as e:
        logger.warning(f"Failed to send ai_scoring_complete notification: {e}")


async def _call_openai_with_retry(
    user_prompt: str,
    job: AIScoringJob,
    temperature: float = 0.3,
    force: bool = False,
    max_retries: int = 3,
) -> str | None:
    """Call OpenAI with exponential backoff retry."""
    import asyncio

    client = get_openai_client()
    delays = [2, 8, 32]

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini" if settings.app_env == "development" else "gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            job.model_used = response.model
            job.prompt_tokens = response.usage.prompt_tokens if response.usage else None
            job.completion_tokens = response.usage.completion_tokens if response.usage else None
            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e)
            logger.warning(f"OpenAI attempt {attempt + 1} failed: {error_str}")

            if "rate_limit" in error_str.lower() or "429" in error_str:
                await asyncio.sleep(60)
                continue

            if attempt < max_retries - 1:
                await asyncio.sleep(delays[attempt])
            else:
                job.status = "failed"
                job.error_message = f"OpenAI error after {max_retries} retries: {error_str}"
                return None

    return None
