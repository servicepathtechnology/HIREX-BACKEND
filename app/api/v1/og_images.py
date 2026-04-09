"""OG image endpoints — score cards, profile cards, task previews."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.task import Submission, Task
from app.models.user import User
from app.og.score_card_generator import (
    generate_profile_card,
    generate_score_card,
    generate_task_card,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/og", tags=["og-images"])


@router.get("/score-card/{submission_id}")
async def get_score_card(
    submission_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    sub_result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = sub_result.scalar_one_or_none()
    if not submission or submission.total_score is None:
        raise HTTPException(status_code=404, detail="Submission not found or not scored.")

    task_result = await db.execute(select(Task).where(Task.id == submission.task_id))
    task = task_result.scalar_one_or_none()

    user_result = await db.execute(select(User).where(User.id == submission.candidate_id))
    user = user_result.scalar_one_or_none()

    count_result = await db.execute(
        select(func.count(Submission.id)).where(
            Submission.task_id == submission.task_id,
            Submission.status == "scored",
        )
    )
    total = count_result.scalar() or 1

    try:
        image_bytes = generate_score_card(
            candidate_name=user.full_name if user else "HireX Candidate",
            task_title=task.title if task else "Task",
            domain=task.domain if task else "General",
            score=submission.total_score,
            rank=submission.rank or 1,
            total_submissions=total,
        )
    except Exception as e:
        logger.error(f"Score card generation failed: {e}")
        raise HTTPException(status_code=500, detail="Image generation failed.")

    return Response(content=image_bytes, media_type="image/png")


@router.get("/profile/{user_id}")
async def get_profile_card(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    profile = user.candidate_profile
    skill_score = profile.skill_score if profile else 0
    headline = profile.headline if profile else None

    tasks_result = await db.execute(
        select(func.count(Submission.id)).where(
            Submission.candidate_id == user_id,
            Submission.status == "scored",
        )
    )
    tasks_completed = tasks_result.scalar() or 0

    try:
        image_bytes = generate_profile_card(
            full_name=user.full_name,
            headline=headline,
            skill_score=skill_score,
            tasks_completed=tasks_completed,
            domain=None,
        )
    except Exception as e:
        logger.error(f"Profile card generation failed: {e}")
        raise HTTPException(status_code=500, detail="Image generation failed.")

    return Response(content=image_bytes, media_type="image/png")


@router.get("/task/{task_id}")
async def get_task_card(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    try:
        image_bytes = generate_task_card(
            task_title=task.title,
            domain=task.domain,
            difficulty=task.difficulty,
            company_name=task.company_name,
            submission_count=task.submission_count,
        )
    except Exception as e:
        logger.error(f"Task card generation failed: {e}")
        raise HTTPException(status_code=500, detail="Image generation failed.")

    return Response(content=image_bytes, media_type="image/png")
