"""Task recommendations API — Part 4."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/tasks", tags=["recommendations"])


@router.get("/recommended")
async def get_recommended_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Personalised task recommendations for candidate."""
    from backend.recommendations.recommendation_engine import get_recommendations
    tasks = await get_recommendations(db, current_user.id, page=page, page_size=page_size)
    return {
        "items": tasks,
        "page": page,
        "page_size": page_size,
        "has_more": len(tasks) == page_size,
    }
