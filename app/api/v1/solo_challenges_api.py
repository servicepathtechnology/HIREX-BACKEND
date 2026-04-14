"""Part 2 — Daily/Weekly/Monthly Solo Challenges API."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.solo_challenges import (
    DailyChallenge, WeeklyChallenge, MonthlyChallenge,
    UserChallenge, UserStreak, UserPreferences,
)
from app.services.solo_challenge_service import (
    get_or_assign_daily_question,
    get_or_assign_weekly_question,
    get_or_assign_monthly_question,
    get_user_challenge,
    create_user_challenge,
    calculate_xp,
    verify_solo_room_token,
)
from app.services.streak_service import (
    get_or_create_streak,
    record_daily_attempt,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/challenges", tags=["solo_challenges"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChallengeHubResponse(BaseModel):
    daily: dict
    weekly: dict
    monthly: dict
    streak: dict
    recent_completions: list[dict]


class StartChallengeResponse(BaseModel):
    challenge_id: str
    room_url: str
    room_token: str


class SubmitChallengeRequest(BaseModel):
    code: str
    language: str


class UpdatePreferencesRequest(BaseModel):
    weekly_day: Optional[str] = None
    monthly_date: Optional[int] = None
    notification_time: Optional[str] = None
    timezone: Optional[str] = None


# ── Helper serializers ────────────────────────────────────────────────────────

def _serialize_question(q) -> dict:
    if not q:
        return {}
    return {
        "id": str(q.id),
        "title": q.title,
        "difficulty": q.difficulty,
        "problem_statement": q.problem_statement,
        "constraints": q.constraints,
        "input_format": q.input_format,
        "output_format": q.output_format,
        "sample_input_1": q.sample_input_1,
        "sample_output_1": q.sample_output_1,
        "sample_input_2": q.sample_input_2,
        "sample_output_2": q.sample_output_2,
        "time_limit_ms": q.time_limit_ms,
        "memory_limit_mb": q.memory_limit_mb,
        "tags": q.tags or [],
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/hub")
async def get_challenge_hub(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChallengeHubResponse:
    """Return all data needed for the Challenge Hub screen."""
    today = date.today()
    year, week, _ = today.isocalendar()
    month = today.month

    # Daily
    daily_challenge = await get_or_assign_daily_question(db, today)
    daily_uc = None
    if daily_challenge:
        daily_uc = await get_user_challenge(db, current_user.id, "daily", daily_challenge.id)

    # Weekly
    weekly_challenge = await get_or_assign_weekly_question(db, year, week)
    weekly_uc = None
    if weekly_challenge:
        weekly_uc = await get_user_challenge(db, current_user.id, "weekly", weekly_challenge.id)

    # Monthly
    monthly_challenge = await get_or_assign_monthly_question(db, year, month)
    monthly_uc = None
    if monthly_challenge:
        monthly_uc = await get_user_challenge(db, current_user.id, "monthly", monthly_challenge.id)

    # Streak
    streak = await get_or_create_streak(db, current_user.id)

    # Recent completions
    recent_result = await db.execute(
        select(UserChallenge)
        .where(
            UserChallenge.user_id == current_user.id,
            UserChallenge.status == "completed",
        )
        .order_by(UserChallenge.submitted_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()

    return ChallengeHubResponse(
        daily={
            "id": str(daily_challenge.id) if daily_challenge else None,
            "date": str(today),
            "question_title": daily_challenge.question.title if daily_challenge else None,
            "difficulty": "easy",
            "status": daily_uc.status if daily_uc else "not_started",
            "completed": daily_uc.status == "completed" if daily_uc else False,
            "xp_reward": 30,
        },
        weekly={
            "id": str(weekly_challenge.id) if weekly_challenge else None,
            "year": year,
            "week": week,
            "question_title": weekly_challenge.question.title if weekly_challenge else None,
            "difficulty": "medium",
            "status": weekly_uc.status if weekly_uc else "not_started",
            "completed": weekly_uc.status == "completed" if weekly_uc else False,
            "xp_reward": 75,
        },
        monthly={
            "id": str(monthly_challenge.id) if monthly_challenge else None,
            "year": year,
            "month": month,
            "question_title": monthly_challenge.question.title if monthly_challenge else None,
            "difficulty": "hard",
            "status": monthly_uc.status if monthly_uc else "not_started",
            "completed": monthly_uc.status == "completed" if monthly_uc else False,
            "xp_reward": 150,
        },
        streak={
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "grace_day_available": streak.grace_day_available,
        },
        recent_completions=[
            {
                "challenge_type": r.challenge_type,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "score": r.score,
                "xp_earned": r.xp_earned,
            }
            for r in recent
        ],
    )


@router.get("/daily")
async def get_daily_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = date.today()
    daily = await get_or_assign_daily_question(db, today)
    if not daily:
        raise HTTPException(status_code=404, detail="No daily challenge available")

    uc = await get_user_challenge(db, current_user.id, "daily", daily.id)
    streak = await get_or_create_streak(db, current_user.id)

    return {
        "id": str(daily.id),
        "date": str(today),
        "question": _serialize_question(daily.question),
        "difficulty": "easy",
        "estimated_time_minutes": 15,
        "xp_reward": 30,
        "user_status": uc.status if uc else "not_started",
        "completed": uc.status == "completed" if uc else False,
        "streak": {
            "current": streak.current_streak,
            "longest": streak.longest_streak,
        },
    }


@router.post("/daily/start")
async def start_daily_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartChallengeResponse:
    today = date.today()
    daily = await get_or_assign_daily_question(db, today)
    if not daily:
        raise HTTPException(status_code=404, detail="No daily challenge available")

    # Check if already completed
    uc = await get_user_challenge(db, current_user.id, "daily", daily.id)
    if uc and uc.status == "completed":
        raise HTTPException(status_code=400, detail="Already completed today's challenge")

    # Create or reuse user challenge
    if not uc:
        uc = await create_user_challenge(db, current_user.id, "daily", daily.id, daily.question_id)
        await db.commit()

    # Record daily attempt for streak
    await record_daily_attempt(db, current_user.id, today)
    await db.commit()

    return StartChallengeResponse(
        challenge_id=str(uc.id),
        room_url=uc.room_url,
        room_token=uc.room_token,
    )


@router.get("/weekly")
async def get_weekly_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = date.today()
    year, week, _ = today.isocalendar()
    weekly = await get_or_assign_weekly_question(db, year, week)
    if not weekly:
        raise HTTPException(status_code=404, detail="No weekly challenge available")

    uc = await get_user_challenge(db, current_user.id, "weekly", weekly.id)

    # Get user preferences for weekly day
    pref_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = pref_result.scalar_one_or_none()

    return {
        "id": str(weekly.id),
        "year": year,
        "week": week,
        "question": _serialize_question(weekly.question),
        "difficulty": "medium",
        "estimated_time_minutes": 30,
        "xp_reward": 75,
        "user_status": uc.status if uc else "not_started",
        "completed": uc.status == "completed" if uc else False,
        "weekly_day": prefs.weekly_day if prefs else None,
    }


@router.post("/weekly/start")
async def start_weekly_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartChallengeResponse:
    today = date.today()
    year, week, _ = today.isocalendar()
    weekly = await get_or_assign_weekly_question(db, year, week)
    if not weekly:
        raise HTTPException(status_code=404, detail="No weekly challenge available")

    uc = await get_user_challenge(db, current_user.id, "weekly", weekly.id)
    if uc and uc.status == "completed":
        raise HTTPException(status_code=400, detail="Already completed this week's challenge")

    if not uc:
        uc = await create_user_challenge(db, current_user.id, "weekly", weekly.id, weekly.question_id)
        await db.commit()

    return StartChallengeResponse(
        challenge_id=str(uc.id),
        room_url=uc.room_url,
        room_token=uc.room_token,
    )


@router.get("/monthly")
async def get_monthly_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = date.today()
    year, month = today.year, today.month
    monthly = await get_or_assign_monthly_question(db, year, month)
    if not monthly:
        raise HTTPException(status_code=404, detail="No monthly challenge available")

    uc = await get_user_challenge(db, current_user.id, "monthly", monthly.id)

    pref_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = pref_result.scalar_one_or_none()

    return {
        "id": str(monthly.id),
        "year": year,
        "month": month,
        "question": _serialize_question(monthly.question),
        "difficulty": "hard",
        "estimated_time_minutes": 60,
        "xp_reward": 150,
        "user_status": uc.status if uc else "not_started",
        "completed": uc.status == "completed" if uc else False,
        "monthly_date": prefs.monthly_date if prefs else None,
    }


@router.post("/monthly/start")
async def start_monthly_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartChallengeResponse:
    today = date.today()
    year, month = today.year, today.month
    monthly = await get_or_assign_monthly_question(db, year, month)
    if not monthly:
        raise HTTPException(status_code=404, detail="No monthly challenge available")

    uc = await get_user_challenge(db, current_user.id, "monthly", monthly.id)
    if uc and uc.status == "completed":
        raise HTTPException(status_code=400, detail="Already completed this month's challenge")

    if not uc:
        uc = await create_user_challenge(db, current_user.id, "monthly", monthly.id, monthly.question_id)
        await db.commit()

    return StartChallengeResponse(
        challenge_id=str(uc.id),
        room_url=uc.room_url,
        room_token=uc.room_token,
    )


@router.get("/streaks/me")
async def get_my_streak(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    streak = await get_or_create_streak(db, current_user.id)
    return {
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "grace_day_available": streak.grace_day_available,
        "last_activity_date": str(streak.last_activity_date) if streak.last_activity_date else None,
    }


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
        await db.commit()

    return {
        "weekly_day": prefs.weekly_day,
        "monthly_date": prefs.monthly_date,
        "notification_time": prefs.notification_time,
        "timezone": prefs.timezone,
        "notifications_enabled": prefs.notifications_enabled,
    }


@router.patch("/preferences")
async def update_preferences(
    payload: UpdatePreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    if payload.weekly_day is not None:
        prefs.weekly_day = payload.weekly_day
    if payload.monthly_date is not None:
        prefs.monthly_date = payload.monthly_date
    if payload.notification_time is not None:
        prefs.notification_time = payload.notification_time
    if payload.timezone is not None:
        prefs.timezone = payload.timezone

    await db.commit()
    return {"status": "updated"}


# ── Solo Room endpoints (authenticated via challenge JWT) ────────────────────

@router.get("/solo/{challenge_type}/{challenge_id}")
async def get_solo_room_data(
    challenge_type: str,
    challenge_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint for Solo Coding Room — authenticated via challenge JWT."""
    try:
        payload = verify_solo_room_token(token)
        token_challenge_id = payload.get("challenge_id")
        if str(challenge_id) != token_challenge_id:
            raise HTTPException(status_code=403, detail="Token mismatch")
        user_id = UUID(payload["user_id"])
        question_id = UUID(payload["question_id"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get question
    from app.models.challenges import Question
    q_result = await db.execute(select(Question).where(Question.id == question_id))
    question = q_result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "challenge_type": challenge_type,
        "challenge_id": str(challenge_id),
        "question": _serialize_question(question),
    }


@router.post("/solo/{challenge_type}/{challenge_id}/submit")
async def submit_solo_challenge(
    challenge_type: str,
    challenge_id: UUID,
    payload: SubmitChallengeRequest,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit solution from Solo Coding Room."""
    try:
        token_payload = verify_solo_room_token(token)
        if str(challenge_id) != token_payload.get("challenge_id"):
            raise HTTPException(status_code=403, detail="Token mismatch")
        user_id = UUID(token_payload["user_id"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user challenge
    uc_result = await db.execute(
        select(UserChallenge).where(UserChallenge.id == challenge_id)
    )
    uc = uc_result.scalar_one_or_none()
    if not uc or uc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if uc.status == "completed":
        raise HTTPException(status_code=400, detail="Already submitted")

    # Mock evaluation (replace with Judge0 in production)
    score = 85  # Mock score
    tests_passed = 8
    tests_total = 10

    uc.status = "completed"
    uc.submitted_at = datetime.utcnow()
    uc.code_content = payload.code
    uc.language = payload.language
    uc.score = score
    uc.tests_passed = tests_passed
    uc.tests_total = tests_total
    uc.result_status = "accepted" if score >= 60 else "wrong_answer"
    uc.xp_earned = calculate_xp(challenge_type, score)

    # Award XP to user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.xp_points = (user.xp_points or 0) + uc.xp_earned

    await db.commit()

    return {
        "status": "completed",
        "score": score,
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "xp_earned": uc.xp_earned,
    }
