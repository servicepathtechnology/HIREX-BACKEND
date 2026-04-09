"""Recruiter Candidates API — candidate deep dive (POW profile view for recruiters)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter
from app.models.user import User
from app.schemas.tasks import POWProfileResponse
from app.api.v1.profile import _build_pow_profile

router = APIRouter(prefix="/recruiter/candidates", tags=["recruiter-candidates"])


@router.get("/{user_id}", response_model=POWProfileResponse)
async def get_candidate_deep_dive(
    user_id: UUID,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> POWProfileResponse:
    """Full POW profile of a candidate — recruiter view."""
    result = await db.execute(select(User).where(User.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if candidate.role != "candidate":
        raise HTTPException(status_code=400, detail="User is not a candidate.")

    return await _build_pow_profile(candidate, db)
