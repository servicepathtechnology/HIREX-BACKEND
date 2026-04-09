"""Recruiter Submissions API — view, score, shortlist, reject submissions."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter
from app.models.user import User, CandidateProfile
from app.models.task import Task, Submission
from app.models.recruiter import PipelineEntry
from app.schemas.recruiter import (
    ScoreSubmissionRequest, RecruiterSubmissionResponse,
    PaginatedRecruiterSubmissionsResponse,
)
from app.services.rank_service import recalculate_ranks, update_candidate_skill_score
from app.services.notification_service import notify_submission_scored, notify_shortlisted

router = APIRouter(prefix="/recruiter", tags=["recruiter-submissions"])


async def _build_submission_response(
    sub: Submission, db: AsyncSession
) -> RecruiterSubmissionResponse:
    # Get candidate info
    user_result = await db.execute(
        select(User, CandidateProfile)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == User.id)
        .where(User.id == sub.candidate_id)
    )
    row = user_result.first()
    candidate_name = None
    candidate_avatar = None
    if row:
        user_obj, profile_obj = row
        is_public = getattr(profile_obj, "public_profile", True) if profile_obj else True
        if is_public:
            candidate_name = user_obj.full_name
            candidate_avatar = user_obj.avatar_url

    return RecruiterSubmissionResponse(
        id=sub.id,
        task_id=sub.task_id,
        candidate_id=sub.candidate_id,
        candidate_name=candidate_name,
        candidate_avatar=candidate_avatar,
        status=sub.status,
        text_content=sub.text_content,
        code_content=sub.code_content,
        code_language=sub.code_language,
        file_urls=sub.file_urls,
        link_url=sub.link_url,
        recording_url=sub.recording_url,
        notes=sub.notes,
        submitted_at=sub.submitted_at,
        total_score=sub.total_score,
        rank=sub.rank,
        percentile=sub.percentile,
        recruiter_feedback=sub.recruiter_feedback,
        time_spent_minutes=sub.time_spent_minutes,
        is_shortlisted=sub.is_shortlisted,
        criterion_scores=None,  # stored separately; fetched via task evaluation_criteria
        ai_summary=sub.ai_summary,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


@router.get("/tasks/{task_id}/submissions", response_model=PaginatedRecruiterSubmissionsResponse)
async def list_task_submissions(
    task_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    sort: str = Query("most_recent", pattern="^(highest_score|lowest_score|most_recent|oldest|time_spent)$"),
    score_min: Optional[float] = Query(None),
    score_max: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> PaginatedRecruiterSubmissionsResponse:
    # Verify task ownership
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")

    query = select(Submission).where(
        Submission.task_id == task_id,
        Submission.status != "draft",
    )

    if status_filter == "pending":
        query = query.where(Submission.status == "submitted")
    elif status_filter == "scored":
        query = query.where(Submission.status == "scored")
    elif status_filter == "shortlisted":
        query = query.where(Submission.is_shortlisted == True)
    elif status_filter and status_filter != "all":
        query = query.where(Submission.status == status_filter)

    if score_min is not None:
        query = query.where(Submission.total_score >= score_min)
    if score_max is not None:
        query = query.where(Submission.total_score <= score_max)

    if sort == "highest_score":
        query = query.order_by(Submission.total_score.desc().nullslast())
    elif sort == "lowest_score":
        query = query.order_by(Submission.total_score.asc().nullslast())
    elif sort == "oldest":
        query = query.order_by(Submission.submitted_at.asc())
    elif sort == "time_spent":
        query = query.order_by(Submission.time_spent_minutes.asc().nullslast())
    else:
        query = query.order_by(Submission.submitted_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    subs = result.scalars().all()

    items = []
    for sub in subs:
        items.append(await _build_submission_response(sub, db))

    return PaginatedRecruiterSubmissionsResponse(
        items=items, total=total, page=page, page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


@router.get("/submissions/{submission_id}", response_model=RecruiterSubmissionResponse)
async def get_submission(
    submission_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterSubmissionResponse:
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    return await _build_submission_response(sub, db)


@router.put("/submissions/{submission_id}/score", response_model=RecruiterSubmissionResponse)
async def score_submission(
    submission_id: UUID,
    payload: ScoreSubmissionRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterSubmissionResponse:
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Validate weights sum to 100
    total_weight = sum(c.weight for c in payload.criterion_scores)
    if abs(total_weight - 100) > 0.5:
        raise HTTPException(status_code=400, detail=f"Criterion weights must sum to 100. Got {total_weight}.")

    # Calculate weighted total score
    total_score = sum(c.score * (c.weight / 100) for c in payload.criterion_scores)
    total_score = round(total_score, 2)

    # Store criterion scores in evaluation_criteria field (reuse JSONB)
    criterion_data = [
        {"name": c.criterion_name, "score": c.score, "weight": c.weight}
        for c in payload.criterion_scores
    ]

    sub.total_score = total_score
    sub.recruiter_feedback = payload.recruiter_feedback
    sub.status = "scored"
    # Store per-criterion scores in the submission's evaluation_criteria
    # We use a separate approach — store in notes as JSON for now
    # (proper column would be added in a future migration)

    await db.flush()

    # Recalculate ranks for all scored submissions in this task
    await recalculate_ranks(db, task.id)

    # Refresh to get updated rank
    await db.refresh(sub)

    # Update candidate skill score
    total_scored_result = await db.execute(
        select(func.count()).where(
            Submission.task_id == task.id,
            Submission.status == "scored",
        )
    )
    total_scored = total_scored_result.scalar() or 1

    try:
        from backend.scoring.skill_score_engine import update_skill_score_v2
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
    except Exception:
        await update_candidate_skill_score(
            db=db,
            candidate_id=sub.candidate_id,
            domain=task.domain,
            total_score=total_score,
            rank=sub.rank or 1,
            total_scored=total_scored,
        )

    # Notify candidate (in-app + FCM push)
    await notify_submission_scored(
        db=db,
        candidate_id=sub.candidate_id,
        task_id=task.id,
        task_title=task.title,
        total_score=total_score,
        submission_id=sub.id,
    )
    try:
        from backend.notifications.fcm_service import push_submission_scored
        await push_submission_scored(db, sub.candidate_id, task.title, total_score, sub.id)
    except Exception:
        pass

    # Shortlist if requested
    if payload.shortlist:
        sub.is_shortlisted = True
        await _create_pipeline_entry(db, current_user.id, sub, task)
        company = task.company_name or "the company"
        await notify_shortlisted(
            db=db,
            candidate_id=sub.candidate_id,
            task_id=task.id,
            task_title=task.title,
            company_name=company,
            submission_id=sub.id,
        )
        try:
            from backend.notifications.fcm_service import push_shortlisted
            await push_shortlisted(db, sub.candidate_id, company, task.title, task.id)
        except Exception:
            pass

    await db.flush()
    return await _build_submission_response(sub, db)


@router.put("/submissions/{submission_id}/shortlist", response_model=RecruiterSubmissionResponse)
async def shortlist_submission(
    submission_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterSubmissionResponse:
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Check if already in pipeline
    existing = await db.execute(
        select(PipelineEntry).where(
            PipelineEntry.recruiter_id == current_user.id,
            PipelineEntry.candidate_id == sub.candidate_id,
            PipelineEntry.task_id == task.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already in pipeline.")

    sub.is_shortlisted = True
    await _create_pipeline_entry(db, current_user.id, sub, task)

    company = task.company_name or "the company"
    await notify_shortlisted(
        db=db,
        candidate_id=sub.candidate_id,
        task_id=task.id,
        task_title=task.title,
        company_name=company,
        submission_id=sub.id,
    )
    try:
        from backend.notifications.fcm_service import push_shortlisted
        await push_shortlisted(db, sub.candidate_id, company, task.title, task.id)
    except Exception:
        pass

    await db.flush()
    return await _build_submission_response(sub, db)


@router.put("/submissions/{submission_id}/reject", response_model=RecruiterSubmissionResponse)
async def reject_submission(
    submission_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterSubmissionResponse:
    sub_result = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    task_result = await db.execute(select(Task).where(Task.id == sub.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    sub.status = "rejected"
    await db.flush()
    return await _build_submission_response(sub, db)


async def _create_pipeline_entry(
    db: AsyncSession,
    recruiter_id: UUID,
    sub: Submission,
    task: Task,
) -> PipelineEntry:
    entry = PipelineEntry(
        recruiter_id=recruiter_id,
        candidate_id=sub.candidate_id,
        task_id=task.id,
        submission_id=sub.id,
        stage="shortlisted",
    )
    db.add(entry)
    await db.flush()
    return entry
