"""Tasks API — candidates browse tasks, bookmark, and view leaderboard."""

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.task import Task, Bookmark, Submission
from app.schemas.tasks import (
    TaskResponse, PaginatedTasksResponse,
    BookmarkToggleRequest, BookmarkToggleResponse,
    LeaderboardResponse, LeaderboardEntryResponse,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Track view rate limiting in-memory (production: use Redis)
_view_tracker: dict = {}


def _build_task_response(task: Task, is_bookmarked: bool = False,
                          submission: Optional[Submission] = None) -> TaskResponse:
    data = {
        "id": task.id,
        "recruiter_id": task.recruiter_id,
        "title": task.title,
        "slug": task.slug,
        "description": task.description,
        "problem_statement": task.problem_statement,
        "evaluation_criteria": task.evaluation_criteria,
        "domain": task.domain,
        "difficulty": task.difficulty,
        "task_type": task.task_type,
        "submission_types": task.submission_types or [],
        "max_file_size_mb": task.max_file_size_mb or 10,
        "allowed_file_types": task.allowed_file_types,
        "deadline": task.deadline,
        "max_submissions": task.max_submissions,
        "is_published": task.is_published,
        "is_active": task.is_active,
        "skills_tested": task.skills_tested or [],
        "estimated_hours": task.estimated_hours,
        "company_visible": task.company_visible,
        "company_name": task.company_name if task.company_visible else None,
        "prize_or_opportunity": task.prize_or_opportunity,
        "view_count": task.view_count,
        "submission_count": task.submission_count,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "is_bookmarked": is_bookmarked,
        "candidate_submission_id": submission.id if submission else None,
        "candidate_submission_status": submission.status if submission else None,
    }
    return TaskResponse(**data)


@router.get("", response_model=PaginatedTasksResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    domain: Optional[str] = None,
    difficulty: Optional[str] = None,
    sort: str = Query("latest", pattern="^(latest|deadline_soon|most_popular|best_match)$"),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedTasksResponse:
    query = select(Task).where(Task.is_active == True, Task.is_published == True)

    if domain:
        query = query.where(Task.domain == domain.lower())
    if difficulty:
        query = query.where(Task.difficulty == difficulty.lower())
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                Task.title.ilike(term),
                Task.description.ilike(term),
                Task.domain.ilike(term),
            )
        )

    if sort == "latest":
        query = query.order_by(Task.created_at.desc())
    elif sort == "deadline_soon":
        query = query.where(Task.deadline > datetime.utcnow()).order_by(Task.deadline.asc())
    elif sort == "most_popular":
        query = query.order_by(Task.submission_count.desc())
    else:
        query = query.order_by(Task.created_at.desc())

    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    tasks = result.scalars().all()

    # Get bookmarks for current user
    bookmark_result = await db.execute(
        select(Bookmark.task_id).where(Bookmark.candidate_id == current_user.id)
    )
    bookmarked_ids = set(bookmark_result.scalars().all())

    # Get submissions for current user
    sub_result = await db.execute(
        select(Submission).where(
            Submission.candidate_id == current_user.id,
            Submission.task_id.in_([t.id for t in tasks]),
        )
    )
    submissions_map = {s.task_id: s for s in sub_result.scalars().all()}

    items = [
        _build_task_response(
            t,
            is_bookmarked=t.id in bookmarked_ids,
            submission=submissions_map.get(t.id),
        )
        for t in tasks
    ]

    return PaginatedTasksResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


@router.get("/{id}", response_model=TaskResponse)
async def get_task(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    result = await db.execute(select(Task).where(Task.id == id, Task.is_active == True))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    bookmark_result = await db.execute(
        select(Bookmark).where(
            Bookmark.candidate_id == current_user.id,
            Bookmark.task_id == id,
        )
    )
    is_bookmarked = bookmark_result.scalar_one_or_none() is not None

    sub_result = await db.execute(
        select(Submission).where(
            Submission.candidate_id == current_user.id,
            Submission.task_id == id,
        )
    )
    submission = sub_result.scalar_one_or_none()

    return _build_task_response(task, is_bookmarked=is_bookmarked, submission=submission)


@router.post("/{id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def increment_view(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Increment view count — rate limited once per user per task per 24h."""
    key = f"{current_user.id}:{id}"
    now = datetime.utcnow()
    last_view = _view_tracker.get(key)
    if last_view and (now - last_view).total_seconds() < 86400:
        return

    result = await db.execute(select(Task).where(Task.id == id))
    task = result.scalar_one_or_none()
    if task:
        task.view_count = (task.view_count or 0) + 1
        _view_tracker[key] = now
        await db.flush()


@router.get("/{id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    task_result = await db.execute(select(Task).where(Task.id == id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    subs_result = await db.execute(
        select(Submission).where(
            Submission.task_id == id,
            Submission.status == "scored",
            Submission.total_score.isnot(None),
        ).order_by(Submission.total_score.desc())
    )
    all_scored = subs_result.scalars().all()
    total_scored = len(all_scored)

    # Paginate
    offset = (page - 1) * page_size
    page_subs = all_scored[offset: offset + page_size]

    # Get candidate info
    candidate_ids = [s.candidate_id for s in page_subs]
    from app.models.user import User as UserModel, CandidateProfile
    users_result = await db.execute(
        select(UserModel, CandidateProfile)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == UserModel.id)
        .where(UserModel.id.in_(candidate_ids))
    )
    user_map = {row[0].id: (row[0], row[1]) for row in users_result.all()}

    entries = []
    for sub in page_subs:
        user_data = user_map.get(sub.candidate_id)
        user_obj = user_data[0] if user_data else None
        profile_obj = user_data[1] if user_data else None
        is_public = profile_obj.public_profile if profile_obj and hasattr(profile_obj, 'public_profile') else True
        is_current = sub.candidate_id == current_user.id

        entries.append(LeaderboardEntryResponse(
            rank=sub.rank or 0,
            candidate_id=sub.candidate_id,
            candidate_name=user_obj.full_name if (user_obj and is_public) else "Anonymous Candidate",
            candidate_avatar=user_obj.avatar_url if (user_obj and is_public) else None,
            total_score=sub.total_score or 0,
            percentile=sub.percentile or 0,
            is_current_user=is_current,
            is_anonymous=not is_public,
        ))

    # Current user entry (always include even if not in page)
    current_user_entry = None
    current_sub = next((s for s in all_scored if s.candidate_id == current_user.id), None)
    if current_sub and not any(e.is_current_user for e in entries):
        current_user_entry = LeaderboardEntryResponse(
            rank=current_sub.rank or 0,
            candidate_id=current_sub.candidate_id,
            candidate_name=current_user.full_name,
            candidate_avatar=current_user.avatar_url,
            total_score=current_sub.total_score or 0,
            percentile=current_sub.percentile or 0,
            is_current_user=True,
            is_anonymous=False,
        )

    return LeaderboardResponse(
        task_id=task.id,
        task_title=task.title,
        task_domain=task.domain,
        total_scored=total_scored,
        entries=entries,
        current_user_entry=current_user_entry,
    )
