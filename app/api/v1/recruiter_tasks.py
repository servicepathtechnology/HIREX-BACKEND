"""Recruiter Tasks API — create, edit, publish, pause, close, duplicate tasks."""

import re
import uuid as uuid_lib
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter
from app.models.user import User
from app.models.task import Task, Submission
from app.models.recruiter import RecruiterAnalytics
from app.schemas.recruiter import (
    CreateTaskRequest, UpdateTaskRequest,
    RecruiterTaskResponse, PaginatedRecruiterTasksResponse,
    TaskStatsResponse, RecruiterDashboardResponse,
    DashboardStatsResponse, RecentSubmissionItem,
)

router = APIRouter(prefix="/recruiter", tags=["recruiter-tasks"])

DEFAULT_CRITERIA = [
    {"name": "Accuracy", "weight": 40, "description": "Does the solution correctly solve the stated problem?"},
    {"name": "Approach & Thinking", "weight": 30, "description": "Is the logic clear, well-reasoned, and structured?"},
    {"name": "Completeness", "weight": 20, "description": "Does it address all stated requirements?"},
    {"name": "Efficiency / Speed", "weight": 10, "description": "Is the solution clean and optimally written?"},
]


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return f"{slug}-{uuid_lib.uuid4().hex[:8]}"


def _to_response(task: Task) -> RecruiterTaskResponse:
    return RecruiterTaskResponse(
        id=task.id,
        recruiter_id=task.recruiter_id,
        title=task.title,
        slug=task.slug,
        description=task.description,
        problem_statement=task.problem_statement,
        evaluation_criteria=task.evaluation_criteria,
        domain=task.domain,
        difficulty=task.difficulty,
        task_type=task.task_type,
        submission_types=task.submission_types or [],
        max_file_size_mb=task.max_file_size_mb or 10,
        allowed_file_types=task.allowed_file_types,
        deadline=task.deadline,
        max_submissions=task.max_submissions,
        is_published=task.is_published,
        is_active=task.is_active,
        skills_tested=task.skills_tested or [],
        estimated_hours=task.estimated_hours,
        company_visible=task.company_visible,
        company_name=task.company_name,
        prize_or_opportunity=task.prize_or_opportunity,
        tier=getattr(task, "tier", "standard") or "standard",
        view_count=task.view_count,
        submission_count=task.submission_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=RecruiterDashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterDashboardResponse:
    now = datetime.utcnow()

    # Active tasks
    active_result = await db.execute(
        select(Task).where(
            Task.recruiter_id == current_user.id,
            Task.is_published == True,
            Task.is_active == True,
            Task.deadline > now,
        ).order_by(Task.deadline.asc())
    )
    active_tasks = active_result.scalars().all()
    active_task_ids = [t.id for t in active_tasks]

    # Total submissions across active tasks
    total_subs = sum(t.submission_count or 0 for t in active_tasks)

    # Pending review
    pending = 0
    if active_task_ids:
        pending_result = await db.execute(
            select(func.count()).where(
                Submission.task_id.in_(active_task_ids),
                Submission.status == "submitted",
            )
        )
        pending = pending_result.scalar() or 0

    # Hires made
    from app.models.recruiter import PipelineEntry
    hires_result = await db.execute(
        select(func.count()).where(
            PipelineEntry.recruiter_id == current_user.id,
            PipelineEntry.stage == "hired",
        )
    )
    hires = hires_result.scalar() or 0

    stats = DashboardStatsResponse(
        active_tasks=len(active_tasks),
        total_submissions=total_subs,
        pending_review=pending,
        hires_made=hires,
    )

    # Recent submissions (last 10 across all recruiter tasks)
    all_task_ids_result = await db.execute(
        select(Task.id).where(Task.recruiter_id == current_user.id)
    )
    all_task_ids = all_task_ids_result.scalars().all()

    recent_subs: list[RecentSubmissionItem] = []
    if all_task_ids:
        recent_result = await db.execute(
            select(Submission, Task).join(Task, Task.id == Submission.task_id).where(
                Submission.task_id.in_(all_task_ids),
                Submission.status.in_(["submitted", "scored", "under_review"]),
            ).order_by(Submission.submitted_at.desc()).limit(10)
        )
        for sub, task in recent_result.all():
            recent_subs.append(RecentSubmissionItem(
                submission_id=sub.id,
                task_id=task.id,
                task_title=task.title,
                candidate_name=None,
                candidate_avatar=None,
                submitted_at=sub.submitted_at,
                status=sub.status,
            ))

    return RecruiterDashboardResponse(
        stats=stats,
        active_tasks=[_to_response(t) for t in active_tasks[:10]],
        recent_submissions=recent_subs,
    )


# ── Task CRUD ─────────────────────────────────────────────────────────────────

@router.post("/tasks", response_model=RecruiterTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: CreateTaskRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterTaskResponse:
    slug = _slugify(payload.title)
    criteria = payload.evaluation_criteria or DEFAULT_CRITERIA

    # Normalize task_type to enum value
    task_type_map = {
        'code challenge': 'code', 'design challenge': 'design',
        'case study': 'case_study', 'business problem': 'business',
        'product task': 'product', 'writing task': 'writing',
    }
    raw_type = payload.task_type.lower()
    task_type = task_type_map.get(raw_type, raw_type.replace(" ", "_"))

    task = Task(
        recruiter_id=current_user.id,
        title=payload.title,
        slug=slug,
        description=payload.description or "",
        problem_statement=payload.problem_statement or "",
        evaluation_criteria=criteria,
        domain=payload.domain.lower(),
        difficulty=payload.difficulty.lower(),
        task_type=task_type,
        submission_types=payload.submission_types or [],
        max_file_size_mb=payload.max_file_size_mb,
        allowed_file_types=payload.allowed_file_types,
        deadline=payload.deadline or (datetime.utcnow() + timedelta(days=7)),
        max_submissions=payload.max_submissions,
        is_published=False,
        is_active=True,
        skills_tested=payload.skills_tested,
        estimated_hours=payload.estimated_hours,
        company_visible=payload.company_visible,
        company_name=payload.company_name,
        prize_or_opportunity=payload.prize_or_opportunity,
        tier=payload.tier,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return _to_response(task)


@router.get("/tasks", response_model=PaginatedRecruiterTasksResponse)
async def list_my_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> PaginatedRecruiterTasksResponse:
    query = select(Task).where(Task.recruiter_id == current_user.id)
    now = datetime.utcnow()

    if status_filter == "active":
        query = query.where(Task.is_published == True, Task.is_active == True, Task.deadline > now)
    elif status_filter == "closed":
        query = query.where(Task.is_published == True, Task.deadline <= now)
    elif status_filter == "draft":
        query = query.where(Task.is_published == False)
    elif status_filter == "paused":
        query = query.where(Task.is_published == True, Task.is_active == False)

    query = query.order_by(Task.updated_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    tasks = result.scalars().all()

    return PaginatedRecruiterTasksResponse(
        items=[_to_response(t) for t in tasks],
        total=total, page=page, page_size=page_size,
        has_more=(offset + len(tasks)) < total,
    )


@router.get("/tasks/{task_id}", response_model=RecruiterTaskResponse)
async def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterTaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return _to_response(task)


@router.put("/tasks/{task_id}", response_model=RecruiterTaskResponse)
async def update_task(
    task_id: UUID,
    payload: UpdateTaskRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterTaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    RESTRICTED_AFTER_PUBLISH = {"title", "problem_statement", "evaluation_criteria"}
    update_data = payload.model_dump(exclude_none=True)

    if task.is_published:
        for field in RESTRICTED_AFTER_PUBLISH:
            if field in update_data:
                raise HTTPException(
                    status_code=403,
                    detail=f"Field '{field}' cannot be changed after task is published.",
                )
        # Deadline can only be extended
        if "deadline" in update_data and update_data["deadline"] < task.deadline:
            raise HTTPException(status_code=400, detail="Cannot shorten deadline after publishing.")
        # Max submissions can only increase
        if "max_submissions" in update_data and task.max_submissions is not None:
            if update_data["max_submissions"] < task.submission_count:
                raise HTTPException(status_code=400, detail="Cannot reduce max_submissions below current count.")

    for field, value in update_data.items():
        if field == "domain":
            value = value.lower()
        elif field == "difficulty":
            value = value.lower()
        elif field == "task_type":
            # Map display names to enum values
            task_type_map = {
                'code challenge': 'code', 'design challenge': 'design',
                'case study': 'case_study', 'business problem': 'business',
                'product task': 'product', 'writing task': 'writing',
            }
            normalized = value.lower().replace(" ", "_")
            value = task_type_map.get(value.lower(), normalized)
        setattr(task, field, value)

    task.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(task)
    return _to_response(task)


@router.put("/tasks/{task_id}/pause", response_model=RecruiterTaskResponse)
async def toggle_pause(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterTaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")
    if not task.is_published:
        raise HTTPException(status_code=400, detail="Task is not published.")
    task.is_active = not task.is_active
    task.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(task)
    return _to_response(task)


@router.put("/tasks/{task_id}/close", response_model=RecruiterTaskResponse)
async def close_task(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterTaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")
    if not task.is_published:
        raise HTTPException(status_code=400, detail="Task is not published.")
    task.deadline = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(task)

    # Notify all candidates who submitted that scoring has begun
    try:
        from app.services.notification_service import create_notification
        from backend.notifications.fcm_service import send_push_notification
        subs_result = await db.execute(
            select(Submission).where(
                Submission.task_id == task.id,
                Submission.status.in_(["submitted", "under_review"]),
            )
        )
        submitted_subs = subs_result.scalars().all()
        for sub in submitted_subs:
            await create_notification(
                db=db, user_id=sub.candidate_id, notif_type="task_closed",
                title="Scoring Has Begun",
                body=f"'{task.title}' is now closed. Scoring will begin shortly.",
                data={"task_id": str(task.id), "type": "task_closed"},
            )
            await send_push_notification(
                db, sub.candidate_id,
                title="Scoring Has Begun",
                body=f"'{task.title}' is now closed. Scoring will begin shortly.",
                data={"type": "task_closed", "task_id": str(task.id)},
                notif_type="task_closed",
            )
    except Exception:
        pass

    return _to_response(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.is_published:
        raise HTTPException(status_code=400, detail="Cannot delete a published task.")
    await db.delete(task)
    await db.flush()


@router.post("/tasks/{task_id}/duplicate", response_model=RecruiterTaskResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_task(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> RecruiterTaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")

    new_task = Task(
        recruiter_id=current_user.id,
        title=f"{task.title} (Copy)",
        slug=_slugify(task.title),
        description=task.description,
        problem_statement=task.problem_statement,
        evaluation_criteria=task.evaluation_criteria,
        domain=task.domain,
        difficulty=task.difficulty,
        task_type=task.task_type,
        submission_types=task.submission_types,
        max_file_size_mb=task.max_file_size_mb,
        allowed_file_types=task.allowed_file_types,
        deadline=datetime.utcnow() + timedelta(days=7),
        max_submissions=task.max_submissions,
        is_published=False,
        is_active=True,
        skills_tested=task.skills_tested,
        estimated_hours=task.estimated_hours,
        company_visible=task.company_visible,
        company_name=task.company_name,
        prize_or_opportunity=task.prize_or_opportunity,
        tier=getattr(task, "tier", "standard"),
    )
    db.add(new_task)
    await db.flush()
    await db.refresh(new_task)
    return _to_response(new_task)


@router.get("/tasks/{task_id}/stats", response_model=TaskStatsResponse)
async def get_task_stats(
    task_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> TaskStatsResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")

    from app.models.recruiter import PipelineEntry
    subs_result = await db.execute(
        select(Submission).where(Submission.task_id == task_id)
    )
    subs = subs_result.scalars().all()

    total = len(subs)
    pending = sum(1 for s in subs if s.status == "submitted")
    scored = sum(1 for s in subs if s.status == "scored")
    shortlisted = sum(1 for s in subs if s.is_shortlisted)

    hires_result = await db.execute(
        select(func.count()).where(
            PipelineEntry.task_id == task_id,
            PipelineEntry.stage == "hired",
        )
    )
    hired = hires_result.scalar() or 0

    scored_scores = [s.total_score for s in subs if s.total_score is not None]
    avg = round(sum(scored_scores) / len(scored_scores), 1) if scored_scores else None

    return TaskStatsResponse(
        task_id=task_id,
        total_submissions=total,
        pending_review=pending,
        scored=scored,
        shortlisted=shortlisted,
        hired=hired,
        avg_score=avg,
    )
