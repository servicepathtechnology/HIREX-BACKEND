"""API endpoints for Part 3 — Leaderboards + Tiers."""

import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.challenges import UserElo
from app.models.leaderboard import EloEvent, TierHistory, Season, SeasonResult
from app.services.redis_service import RedisService
from app.schemas.leaderboard import (
    LeaderboardResponse,
    LeaderboardRow,
    UserRankResponse,
    EloHistoryResponse,
    EloBreakdownResponse,
    SeasonResponse,
)

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])
redis_service = RedisService()


async def hydrate_leaderboard_rows(
    db: AsyncSession,
    user_ids: List[str],
    start_rank: int
) -> List[LeaderboardRow]:
    """Fetch user details and build leaderboard rows."""
    rows = []
    
    for idx, user_id_str in enumerate(user_ids):
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            continue
        
        # Get user and ELO data
        result = await db.execute(
            select(User, UserElo)
            .join(UserElo, User.id == UserElo.user_id)
            .where(User.id == user_id)
        )
        row_data = result.first()
        
        if not row_data:
            continue
        
        user, user_elo = row_data
        
        # Calculate win rate
        total_matches = user_elo.matches_played
        win_rate = (user_elo.wins / total_matches * 100) if total_matches > 0 else 0
        
        rows.append(LeaderboardRow(
            rank=start_rank + idx + 1,
            user_id=str(user.id),
            name=user.full_name,
            avatar=user.avatar_url,
            country=user.country,
            elo=user_elo.elo,
            tier=user_elo.tier,
            win_rate=round(win_rate, 1),
            matches_played=total_matches,
        ))
    
    return rows


@router.get("/global", response_model=LeaderboardResponse)
async def get_global_leaderboard(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get global leaderboard ranked by ELO."""
    start = (page - 1) * limit
    end = start + limit - 1
    
    # Try Redis first, fallback to database
    if redis_service.is_available:
        # Get from Redis sorted set
        user_ids_with_scores = await redis_service.zrevrange(
            "lb:global", start, end, withscores=True
        )
        
        # Extract user IDs (every other element)
        user_ids = [user_ids_with_scores[i] for i in range(0, len(user_ids_with_scores), 2)]
        
        # Hydrate rows
        rows = await hydrate_leaderboard_rows(db, user_ids, start)
        
        # Get total count
        total_count = await redis_service.zcard("lb:global")
        
        # Get current user's row
        user_rank = await redis_service.zrevrank("lb:global", str(current_user.id))
    else:
        # Fallback to database query
        result = await db.execute(
            select(User, UserElo)
            .join(UserElo, User.id == UserElo.user_id)
            .order_by(desc(UserElo.elo))
            .limit(limit)
            .offset(start)
        )
        rows_data = result.all()
        
        rows = []
        for idx, (user, user_elo) in enumerate(rows_data):
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            rows.append(LeaderboardRow(
                rank=start + idx + 1,
                user_id=str(user.id),
                name=user.full_name,
                avatar=user.avatar_url,
                country=user.country,
                elo=user_elo.elo,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            ))
        
        # Get total count
        count_result = await db.execute(select(func.count(UserElo.id)))
        total_count = count_result.scalar() or 0
        
        # Get current user's rank
        rank_result = await db.execute(
            select(func.count(UserElo.id))
            .where(UserElo.elo > (
                select(UserElo.elo).where(UserElo.user_id == current_user.id)
            ))
        )
        user_rank = rank_result.scalar()
    
    user_row = None
    if user_rank is not None:
        user_rank += 1  # Convert to 1-indexed
        user_elo_result = await db.execute(
            select(UserElo).where(UserElo.user_id == current_user.id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if user_elo:
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            user_row = LeaderboardRow(
                rank=user_rank,
                user_id=str(current_user.id),
                name=current_user.full_name,
                avatar=current_user.avatar_url,
                country=current_user.country,
                elo=user_elo.elo,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            )
    
    return LeaderboardResponse(
        rows=rows,
        total_count=total_count,
        user_row=user_row,
    )


@router.get("/country", response_model=LeaderboardResponse)
async def get_country_leaderboard(
    country: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get country-specific leaderboard."""
    country_code = country or current_user.country
    
    if not country_code:
        raise HTTPException(status_code=400, detail="Country not specified")
    
    start = (page - 1) * limit
    end = start + limit - 1
    
    # Get from Redis sorted set
    user_ids_with_scores = await redis_service.zrevrange(
        f"lb:country:{country_code}", start, end, withscores=True
    )
    
    user_ids = [user_ids_with_scores[i] for i in range(0, len(user_ids_with_scores), 2)]
    rows = await hydrate_leaderboard_rows(db, user_ids, start)
    
    total_count = await redis_service.zcard(f"lb:country:{country_code}")
    
    # Get current user's country rank
    user_rank = await redis_service.zrevrank(f"lb:country:{country_code}", str(current_user.id))
    user_row = None
    
    if user_rank is not None:
        user_rank += 1
        user_elo_result = await db.execute(
            select(UserElo).where(UserElo.user_id == current_user.id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if user_elo:
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            user_row = LeaderboardRow(
                rank=user_rank,
                user_id=str(current_user.id),
                name=current_user.full_name,
                avatar=current_user.avatar_url,
                country=current_user.country,
                elo=user_elo.elo,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            )
    
    return LeaderboardResponse(
        rows=rows,
        total_count=total_count,
        user_row=user_row,
    )


@router.get("/domain", response_model=LeaderboardResponse)
async def get_domain_leaderboard(
    domain: str = Query("coding"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get domain-specific leaderboard (coding only in v1)."""
    start = (page - 1) * limit
    end = start + limit - 1
    
    user_ids_with_scores = await redis_service.zrevrange(
        f"lb:domain:{domain}", start, end, withscores=True
    )
    
    user_ids = [user_ids_with_scores[i] for i in range(0, len(user_ids_with_scores), 2)]
    rows = await hydrate_leaderboard_rows(db, user_ids, start)
    
    total_count = await redis_service.zcard(f"lb:domain:{domain}")
    
    user_rank = await redis_service.zrevrank(f"lb:domain:{domain}", str(current_user.id))
    user_row = None
    
    if user_rank is not None:
        user_rank += 1
        user_elo_result = await db.execute(
            select(UserElo).where(UserElo.user_id == current_user.id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if user_elo:
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            user_row = LeaderboardRow(
                rank=user_rank,
                user_id=str(current_user.id),
                name=current_user.full_name,
                avatar=current_user.avatar_url,
                country=current_user.country,
                elo=user_elo.coding_elo,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            )
    
    return LeaderboardResponse(
        rows=rows,
        total_count=total_count,
        user_row=user_row,
    )


@router.get("/experience", response_model=LeaderboardResponse)
async def get_experience_leaderboard(
    level: str = Query("junior"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get experience level leaderboard."""
    start = (page - 1) * limit
    end = start + limit - 1
    
    user_ids_with_scores = await redis_service.zrevrange(
        f"lb:exp:{level}", start, end, withscores=True
    )
    
    user_ids = [user_ids_with_scores[i] for i in range(0, len(user_ids_with_scores), 2)]
    rows = await hydrate_leaderboard_rows(db, user_ids, start)
    
    total_count = await redis_service.zcard(f"lb:exp:{level}")
    
    user_rank = await redis_service.zrevrank(f"lb:exp:{level}", str(current_user.id))
    user_row = None
    
    if user_rank is not None:
        user_rank += 1
        user_elo_result = await db.execute(
            select(UserElo).where(UserElo.user_id == current_user.id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if user_elo:
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            user_row = LeaderboardRow(
                rank=user_rank,
                user_id=str(current_user.id),
                name=current_user.full_name,
                avatar=current_user.avatar_url,
                country=current_user.country,
                elo=user_elo.elo,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            )
    
    return LeaderboardResponse(
        rows=rows,
        total_count=total_count,
        user_row=user_row,
    )


@router.get("/weekly", response_model=LeaderboardResponse)
async def get_weekly_leaderboard(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=10, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get weekly leaderboard (ELO gained this week)."""
    start = (page - 1) * limit
    end = start + limit - 1
    
    user_ids_with_scores = await redis_service.zrevrange(
        "lb:weekly", start, end, withscores=True
    )
    
    user_ids = [user_ids_with_scores[i] for i in range(0, len(user_ids_with_scores), 2)]
    rows = await hydrate_leaderboard_rows(db, user_ids, start)
    
    total_count = await redis_service.zcard("lb:weekly")
    
    user_rank = await redis_service.zrevrank("lb:weekly", str(current_user.id))
    user_row = None
    
    if user_rank is not None:
        user_rank += 1
        user_elo_result = await db.execute(
            select(UserElo).where(UserElo.user_id == current_user.id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if user_elo:
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            user_row = LeaderboardRow(
                rank=user_rank,
                user_id=str(current_user.id),
                name=current_user.full_name,
                avatar=current_user.avatar_url,
                country=current_user.country,
                elo=user_elo.weekly_elo_gain,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            )
    
    return LeaderboardResponse(
        rows=rows,
        total_count=total_count,
        user_row=user_row,
    )


@router.get("/monthly", response_model=LeaderboardResponse)
async def get_monthly_leaderboard(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=10, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get monthly leaderboard (ELO gained this month)."""
    start = (page - 1) * limit
    end = start + limit - 1
    
    user_ids_with_scores = await redis_service.zrevrange(
        "lb:monthly", start, end, withscores=True
    )
    
    user_ids = [user_ids_with_scores[i] for i in range(0, len(user_ids_with_scores), 2)]
    rows = await hydrate_leaderboard_rows(db, user_ids, start)
    
    total_count = await redis_service.zcard("lb:monthly")
    
    user_rank = await redis_service.zrevrank("lb:monthly", str(current_user.id))
    user_row = None
    
    if user_rank is not None:
        user_rank += 1
        user_elo_result = await db.execute(
            select(UserElo).where(UserElo.user_id == current_user.id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if user_elo:
            win_rate = (user_elo.wins / user_elo.matches_played * 100) if user_elo.matches_played > 0 else 0
            user_row = LeaderboardRow(
                rank=user_rank,
                user_id=str(current_user.id),
                name=current_user.full_name,
                avatar=current_user.avatar_url,
                country=current_user.country,
                elo=user_elo.monthly_elo_gain,
                tier=user_elo.tier,
                win_rate=round(win_rate, 1),
                matches_played=user_elo.matches_played,
            )
    
    return LeaderboardResponse(
        rows=rows,
        total_count=total_count,
        user_row=user_row,
    )
