"""API endpoints for ELO and user rank data."""

import uuid
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.challenges import UserElo
from app.models.leaderboard import EloEvent, TierHistory, Season, SeasonResult
from app.services.redis_service import RedisService
from app.schemas.leaderboard import (
    UserRankResponse,
    EloHistoryResponse,
    EloBreakdownResponse,
    SeasonResponse,
    EloHistoryItem,
)

router = APIRouter(prefix="/api/elo", tags=["elo"])
redis_service = RedisService()


@router.get("/me", response_model=UserRankResponse)
async def get_my_elo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's full ELO data."""
    # Get user ELO
    result = await db.execute(
        select(UserElo).where(UserElo.user_id == current_user.id)
    )
    user_elo = result.scalar_one_or_none()
    
    if not user_elo:
        raise HTTPException(status_code=404, detail="ELO record not found")
    
    # Get ranks from Redis
    global_rank = await redis_service.zrevrank("lb:global", str(current_user.id))
    global_rank = (global_rank + 1) if global_rank is not None else None
    
    country_rank = None
    if current_user.country:
        country_rank = await redis_service.zrevrank(
            f"lb:country:{current_user.country}",
            str(current_user.id)
        )
        country_rank = (country_rank + 1) if country_rank is not None else None
    
    # Get current season
    season_result = await db.execute(
        select(Season).where(Season.status == "active").order_by(Season.id.desc())
    )
    season = season_result.scalar_one_or_none()
    
    # Calculate days remaining
    days_remaining = None
    if season:
        days_remaining = (season.end_date - datetime.now().date()).days
    
    return UserRankResponse(
        elo=user_elo.elo,
        tier=user_elo.tier,
        global_rank=global_rank,
        country_rank=country_rank,
        weekly_gain=user_elo.weekly_elo_gain,
        monthly_gain=user_elo.monthly_elo_gain,
        placement_matches_remaining=max(0, 10 - user_elo.placement_matches_done),
        season_end_date=season.end_date if season else None,
        days_remaining=days_remaining,
        matches_played=user_elo.matches_played,
        wins=user_elo.wins,
        losses=user_elo.losses,
        draws=user_elo.draws,
        peak_elo=user_elo.peak_elo,
        current_streak=user_elo.current_streak,
    )


@router.get("/{user_id}", response_model=UserRankResponse)
async def get_user_elo(
    user_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Get any user's public ELO data."""
    # Get user ELO
    result = await db.execute(
        select(UserElo).where(UserElo.user_id == user_id)
    )
    user_elo = result.scalar_one_or_none()
    
    if not user_elo:
        raise HTTPException(status_code=404, detail="ELO record not found")
    
    # Get user
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    # Get ranks from Redis
    global_rank = await redis_service.zrevrank("lb:global", str(user_id))
    global_rank = (global_rank + 1) if global_rank is not None else None
    
    country_rank = None
    if user and user.country:
        country_rank = await redis_service.zrevrank(
            f"lb:country:{user.country}",
            str(user_id)
        )
        country_rank = (country_rank + 1) if country_rank is not None else None
    
    return UserRankResponse(
        elo=user_elo.elo,
        tier=user_elo.tier,
        global_rank=global_rank,
        country_rank=country_rank,
        weekly_gain=user_elo.weekly_elo_gain,
        monthly_gain=user_elo.monthly_elo_gain,
        placement_matches_remaining=None,  # Private
        season_end_date=None,
        days_remaining=None,
        matches_played=user_elo.matches_played,
        wins=user_elo.wins,
        losses=user_elo.losses,
        draws=user_elo.draws,
        peak_elo=user_elo.peak_elo,
        current_streak=user_elo.current_streak,
    )


@router.get("/me/history", response_model=EloHistoryResponse)
async def get_my_elo_history(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ELO event history for current user."""
    since = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(EloEvent)
        .where(
            and_(
                EloEvent.user_id == current_user.id,
                EloEvent.created_at >= since
            )
        )
        .order_by(desc(EloEvent.created_at))
    )
    events = result.scalars().all()
    
    items = []
    for event in events:
        opponent_name = None
        if event.opponent_id:
            opponent_result = await db.execute(
                select(User).where(User.id == event.opponent_id)
            )
            opponent = opponent_result.scalar_one_or_none()
            opponent_name = opponent.full_name if opponent else "Unknown"
        
        items.append(EloHistoryItem(
            date=event.created_at,
            elo_before=event.elo_before,
            elo_after=event.elo_after,
            change=event.elo_change,
            source=event.event_type,
            opponent_name=opponent_name,
        ))
    
    return EloHistoryResponse(items=items)


@router.get("/me/breakdown", response_model=EloBreakdownResponse)
async def get_my_elo_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ELO earned by source."""
    # Sum ELO changes by event type
    result = await db.execute(
        select(
            EloEvent.event_type,
            func.sum(EloEvent.elo_change).label("total")
        )
        .where(EloEvent.user_id == current_user.id)
        .group_by(EloEvent.event_type)
    )
    
    breakdown = {row.event_type: row.total for row in result}
    
    # Categorize
    from_1v1 = sum(
        breakdown.get(t, 0)
        for t in ["1v1_win", "1v1_loss", "1v1_draw"]
    )
    from_daily = breakdown.get("daily_complete", 0) + breakdown.get("daily_correct", 0)
    from_weekly = breakdown.get("weekly_complete", 0)
    from_monthly = breakdown.get("monthly_complete", 0)
    from_bonuses = sum(
        breakdown.get(t, 0)
        for t in ["streak_bonus", "placement_bonus"]
    )
    
    return EloBreakdownResponse(
        from_1v1=from_1v1,
        from_daily=from_daily,
        from_weekly=from_weekly,
        from_monthly=from_monthly,
        from_bonuses=from_bonuses,
    )
