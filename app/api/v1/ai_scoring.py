"""AI Scoring API — Part 4."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter, get_current_user
from app.models.part4 import AIScoringJob
from app.models.task import Submission, Task
from app.models.user import User
from app.services.notification_service import create_notification

router = APIRouter(prefix="/ai", tags=["ai-scoring"])


class BulkScoreRequest(BaseModel):
    submission_ids: list[str]


class ApproveAIScoreRequest(BaseModel):
    overrides: Optional[dict] = None  # {criterion_name: overridden_score}
    recruiter_feedback: Optional[str] = None


def _job_to_dict(job: AIScoringJob) -> dict:
    return {
        "id": str(job.id),
        "submission_id": str(job.submission_id),
        "task_id": str(job.task_id),
        "status": job.status,
        "model_used": job.model_used,
        "ai_scores": job.ai_scores,
        "ai_total_score": job.ai_total_score,
        "ai_summary": job.ai_summary,
        "ai_flags": job.ai_flags,
        "recruiter_approved": job.recruiter_approved,
        "recruiter_overrides": job.recruiter_overrides,
        "prompt_tokens": job.prompt_tokens,
        "completion_tokens": job.completion_tokens,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


async def _enqueue_job(db: AsyncSession, submission_id: UUID, task_id: UUID) -> AIScoringJob:
    """Create AI scoring job and enqueue Celery task."""
    # Check if job already exists and is not failed
    existing = await db.execute(
        select(AIScoringJob).where(
            AIScoringJob.submission_id == submission_id,
            AIScoringJob.status.in_(["queued", "processing", "completed"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="AI scoring job already exists for this submission.")

    job = AIScoringJob(submission_id=submission_id, task_id=task_id, status="queued")
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Enqueue Celery task
    try:
        from backend.celery_tasks import score_submission_task
        score_submission_task.delay(str(job.id))
    except Exception as e:
        job.status = "failed"
        job.error_message = f"Failed to enqueue: {e}"
        await db.flush()

    return job


@router.post("/score/{submission_id}")
async def enqueue_ai_score(
    submission_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enqueue AI scoring for a single submission."""
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    if task.tier == "basic":
        raise HTTPException(status_code=400, detail="AI scoring not available for Basic tier tasks.")

    job = await _enqueue_job(db, submission_id, task.id)
    return {"job_id": str(job.id), "status": job.status}


@router.post("/score-bulk")
async def enqueue_bulk_ai_score(
    payload: BulkScoreRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enqueue AI scoring for multiple submissions."""
    job_ids = []
    for sid_str in payload.submission_ids:
        try:
            sid = UUID(sid_str)
        except ValueError:
            continue

        sub_result = await db.execute(select(Submission).where(Submission.id == sid))
        sub = sub_result.scalar_one_or_none()
        if not sub:
            continue

        task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
        task = task_result.scalar_one_or_none()
        if not task or task.recruiter_id != current_user.id or task.tier == "basic":
            continue

        try:
            job = await _enqueue_job(db, sid, task.id)
            job_ids.append(str(job.id))
        except HTTPException:
            pass

    return {"job_ids": job_ids, "count": len(job_ids)}


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Poll AI scoring job status."""
    result = await db.execute(select(AIScoringJob).where(AIScoringJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_to_dict(job)


@router.get("/review/{submission_id}")
async def get_ai_review(
    submission_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full AI review data for the approval screen."""
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    job_result = await db.execute(
        select(AIScoringJob).where(
            AIScoringJob.submission_id == submission_id,
            AIScoringJob.status == "completed",
        ).order_by(AIScoringJob.created_at.desc())
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="No completed AI scoring job found.")

    return {
        "job": _job_to_dict(job),
        "submission": {
            "id": str(sub.id),
            "text_content": sub.text_content,
            "code_content": sub.code_content,
            "notes": sub.notes,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        },
        "task": {
            "id": str(task.id),
            "title": task.title,
            "evaluation_criteria": task.evaluation_criteria,
        },
    }


@router.post("/approve/{submission_id}")
async def approve_ai_scores(
    submission_id: UUID,
    payload: ApproveAIScoreRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve AI scores (with optional overrides) and publish to candidate."""
    from sqlalchemy import func
    from app.services.rank_service import recalculate_ranks
    from backend.scoring.skill_score_engine import update_skill_score_v2
    from backend.notifications.fcm_service import push_submission_scored
    from app.services.notification_service import notify_submission_scored

    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    job_result = await db.execute(
        select(AIScoringJob).where(
            AIScoringJob.submission_id == submission_id,
            AIScoringJob.status == "completed",
        ).order_by(AIScoringJob.created_at.desc())
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="No completed AI scoring job found.")

    # Apply overrides if provided
    ai_scores = job.ai_scores or {}
    overrides = payload.overrides or {}
    final_scores = {}
    for criterion, data in ai_scores.items():
        final_score = overrides.get(criterion, data["score"])
        final_scores[criterion] = final_score

    # Calculate weighted total from evaluation_criteria
    criteria = task.evaluation_criteria if isinstance(task.evaluation_criteria, list) else []
    total_weight = sum(c.get("weight", 0) for c in criteria)
    if total_weight > 0 and final_scores:
        total_score = sum(
            final_scores.get(c["name"], 0) * (c.get("weight", 0) / total_weight)
            for c in criteria
        )
    else:
        total_score = job.ai_total_score or 0

    total_score = round(total_score, 2)

    # Update submission
    sub.total_score = total_score
    sub.status = "scored"
    sub.ai_summary = job.ai_summary
    if payload.recruiter_feedback:
        sub.recruiter_feedback = payload.recruiter_feedback

    # Update job
    job.recruiter_approved = True
    if overrides:
        job.recruiter_overrides = {
            k: {"original_ai_score": ai_scores.get(k, {}).get("score"), "overridden_score": v}
            for k, v in overrides.items()
        }

    await db.flush()

    # Recalculate ranks
    await recalculate_ranks(db, task.id)
    await db.refresh(sub)

    # Update skill score
    total_scored_result = await db.execute(
        select(func.count()).where(
            Submission.task_id == task.id,
            Submission.status == "scored",
        )
    )
    total_scored = total_scored_result.scalar() or 1

    await update_skill_score_v2(
        db=db,
        candidate_id=sub.candidate_id,
        domain=task.domain,
        task_score=total_score,
        rank=sub.rank or 1,
        total_submissions=total_scored,
        difficulty=task.difficulty,
        submission_id=sub.id,
        task_title=task.title,
    )

    # Notify candidate
    await notify_submission_scored(
        db=db, candidate_id=sub.candidate_id, task_id=task.id,
        task_title=task.title, total_score=total_score, submission_id=sub.id,
    )
    await push_submission_scored(db, sub.candidate_id, task.title, total_score, sub.id)

    return {"status": "approved", "total_score": total_score, "submission_id": str(sub.id)}


@router.get("/explanation/{submission_id}", tags=["candidate"])
async def get_score_explanation(
    submission_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """AI score explanation for candidate."""
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if sub.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if sub.status != "scored":
        raise HTTPException(status_code=400, detail="Submission not yet scored.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()

    job_result = await db.execute(
        select(AIScoringJob).where(
            AIScoringJob.submission_id == submission_id,
            AIScoringJob.status == "completed",
            AIScoringJob.recruiter_approved == True,
        ).order_by(AIScoringJob.created_at.desc())
    )
    job = job_result.scalar_one_or_none()

    return {
        "submission_id": str(sub.id),
        "task_title": task.title if task else "",
        "total_score": sub.total_score,
        "rank": sub.rank,
        "percentile": sub.percentile,
        "ai_summary": sub.ai_summary,
        "ai_scores": job.ai_scores if job else None,
        "evaluation_criteria": task.evaluation_criteria if task else [],
    }
