"""Bookmarks API — toggle and list bookmarked tasks."""

from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.task import Bookmark, Task
from app.schemas.tasks import BookmarkToggleRequest, BookmarkToggleResponse, TaskResponse

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.post("", response_model=BookmarkToggleResponse)
async def toggle_bookmark(
    payload: BookmarkToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookmarkToggleResponse:
    result = await db.execute(
        select(Bookmark).where(
            Bookmark.candidate_id == current_user.id,
            Bookmark.task_id == payload.task_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.flush()
        return BookmarkToggleResponse(bookmarked=False, task_id=payload.task_id)
    else:
        bookmark = Bookmark(candidate_id=current_user.id, task_id=payload.task_id)
        db.add(bookmark)
        await db.flush()
        return BookmarkToggleResponse(bookmarked=True, task_id=payload.task_id)


@router.get("", response_model=list[TaskResponse])
async def get_bookmarks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TaskResponse]:
    result = await db.execute(
        select(Task, Bookmark.created_at)
        .join(Bookmark, Bookmark.task_id == Task.id)
        .where(Bookmark.candidate_id == current_user.id, Task.is_active == True)
        .order_by(Bookmark.created_at.desc())
    )
    rows = result.all()
    tasks = [row[0] for row in rows]

    from app.api.v1.tasks import _build_task_response
    return [_build_task_response(t, is_bookmarked=True) for t in tasks]
