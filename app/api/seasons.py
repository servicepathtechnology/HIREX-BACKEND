"""API endpoints for seasons."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.challenges import UserElo
from app.models.leaderboard import Season, SeasonResult
from app.schemas.leaderboard import SeasonResponse

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("/current", response_model=SeasonResponse)
async def get_current_season(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current season info with reset preview."""
    # Get active season
    result = await db.execute(
        select(Season).where(Season.status == "active").order_by(Season.id.desc())
    )
    season = result.scalar_one_or_none()
    
    if not season:
        raise HTTPException(status_code=404, detail="No active season")
    
    # Get user ELO
    elo_result = await db.execute(
        select(UserElo).where(UserElo.user_id == current_user.id)
    )
    user_elo = elo_result.scalar_one_or_none()
    
    if not user_elo:
        raise HTTPException(status_code=404, detail="ELO record not found")
    
    # Calculate days remaining
    days_remaining = (season.end_date - datetime.now().date()).days
    
    # Calculate projected ELO after reset
    current_elo = user_elo.elo
    reset_factor = float(season.reset_factor)
    projected_elo = int(current_elo - (current_elo - 1000) * reset_factor)
    
    return SeasonResponse(
        season_number=season.season_number,
        start_date=season.start_date,
        end_date=season.end_date,
        days_remaining=days_remaining,
        current_elo=current_elo,
        projected_elo_after_reset=projected_elo,
    )


@router.get("/history")
async def get_season_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get past seasons with user's performance."""
    result = await db.execute(
        select(SeasonResult)
        .where(SeasonResult.user_id == current_user.id)
        .order_by(desc(SeasonResult.season_id))
    )
    results = result.scalars().all()
    
    return [
        {
            "season_id": r.season_id,
            "final_elo": r.final_elo,
            "final_tier": r.final_tier,
            "global_rank": r.global_rank,
            "country_rank": r.country_rank,
            "elo_gained": r.elo_gained,
        }
        for r in results
    ]
