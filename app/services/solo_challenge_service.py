"""Solo challenge service — question assignment, room token generation, Judge0 evaluation."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from jose import jwt
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.challenges import Question
from app.models.solo_challenges import (
    DailyChallenge, WeeklyChallenge, MonthlyChallenge,
    UserChallenge, QuestionScheduleHistory,
)

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_SOLO_TOKEN_TTL = 3600  # 60 minutes


# ── Token generation ──────────────────────────────────────────────────────────

def generate_solo_room_token(
    user_id: UUID,
    challenge_type: str,
    challenge_id: UUID,
    question_id: UUID,
) -> str:
    now = int(time.time())
    payload = {
        "user_id": str(user_id),
        "challenge_type": challenge_type,
        "challenge_id": str(challenge_id),
        "question_id": str(question_id),
        "iat": now,
        "exp": now + _SOLO_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.challenge_jwt_secret, algorithm=_ALGORITHM)


def verify_solo_room_token(token: str) -> dict:
    return jwt.decode(token, settings.challenge_jwt_secret, algorithms=[_ALGORITHM])


def build_solo_room_url(challenge_type: str, challenge_id: UUID, token: str) -> str:
    base = settings.challenge_room_base_url.rstrip("/")
    return f"{base}/solo/{challenge_type}/{challenge_id}?token={token}"


# ── Question selection ────────────────────────────────────────────────────────

async def get_or_assign_daily_question(db: AsyncSession, today: date) -> Optional[DailyChallenge]:
    """Get today's daily challenge, assigning one if not yet set."""
    result = await db.execute(
        select(DailyChallenge)
        .options(joinedload(DailyChallenge.question))
        .where(DailyChallenge.challenge_date == today)
    )
    daily = result.scalar_one_or_none()
    if daily:
        return daily

    # Assign a new question
    question = await _pick_question(db, "easy", "daily", days_back=200)
    if not question:
        logger.error("No easy questions available for daily challenge")
        return None

    daily = DailyChallenge(challenge_date=today, question_id=question.id)
    db.add(daily)
    db.add(QuestionScheduleHistory(
        question_id=question.id,
        challenge_type="daily",
        used_date=today,
    ))
    await db.flush()
    # Refresh to load the question relationship
    await db.refresh(daily, ["question"])
    return daily


async def get_or_assign_weekly_question(db: AsyncSession, year: int, week: int) -> Optional[WeeklyChallenge]:
    result = await db.execute(
        select(WeeklyChallenge)
        .options(joinedload(WeeklyChallenge.question))
        .where(
            WeeklyChallenge.year == year,
            WeeklyChallenge.week_number == week,
        )
    )
    weekly = result.scalar_one_or_none()
    if weekly:
        return weekly

    question = await _pick_question(db, "medium", "weekly", days_back=365)
    if not question:
        logger.error("No medium questions available for weekly challenge")
        return None

    weekly = WeeklyChallenge(year=year, week_number=week, question_id=question.id)
    db.add(weekly)
    db.add(QuestionScheduleHistory(
        question_id=question.id,
        challenge_type="weekly",
        used_date=date.today(),
    ))
    await db.flush()
    # Refresh to load the question relationship
    await db.refresh(weekly, ["question"])
    return weekly


async def get_or_assign_monthly_question(db: AsyncSession, year: int, month: int) -> Optional[MonthlyChallenge]:
    result = await db.execute(
        select(MonthlyChallenge)
        .options(joinedload(MonthlyChallenge.question))
        .where(
            MonthlyChallenge.year == year,
            MonthlyChallenge.month == month,
        )
    )
    monthly = result.scalar_one_or_none()
    if monthly:
        return monthly

    question = await _pick_question(db, "hard", "monthly", days_back=365)
    if not question:
        logger.error("No hard questions available for monthly challenge")
        return None

    monthly = MonthlyChallenge(year=year, month=month, question_id=question.id)
    db.add(monthly)
    db.add(QuestionScheduleHistory(
        question_id=question.id,
        challenge_type="monthly",
        used_date=date.today(),
    ))
    await db.flush()
    # Refresh to load the question relationship
    await db.refresh(monthly, ["question"])
    return monthly


async def _pick_question(
    db: AsyncSession,
    difficulty: str,
    challenge_type: str,
    days_back: int,
) -> Optional[Question]:
    """Pick a random active question not used in the last N days."""
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days_back)

    # Get recently used question IDs
    used_result = await db.execute(
        select(QuestionScheduleHistory.question_id).where(
            QuestionScheduleHistory.challenge_type == challenge_type,
            QuestionScheduleHistory.used_date >= cutoff,
        )
    )
    used_ids = {row[0] for row in used_result.fetchall()}

    # Pick random question not in used_ids
    stmt = (
        select(Question)
        .where(
            Question.difficulty == difficulty,
            Question.is_active.is_(True),
        )
        .order_by(func.random())
        .limit(20)
    )
    result = await db.execute(stmt)
    candidates = result.scalars().all()

    for q in candidates:
        if q.id not in used_ids:
            return q

    # Fallback: use any question if all have been used
    if candidates:
        return candidates[0]
    return None


# ── XP calculation ────────────────────────────────────────────────────────────

def calculate_xp(challenge_type: str, score: int) -> int:
    """Calculate XP earned based on challenge type and score."""
    passed = score >= 60
    xp_map = {
        "daily":   (30, 5),
        "weekly":  (75, 10),
        "monthly": (150, 20),
    }
    correct_xp, attempt_xp = xp_map.get(challenge_type, (30, 5))
    return correct_xp if passed else attempt_xp


# ── User challenge helpers ────────────────────────────────────────────────────

async def get_user_challenge(
    db: AsyncSession,
    user_id: UUID,
    challenge_type: str,
    challenge_ref_id: UUID,
) -> Optional[UserChallenge]:
    result = await db.execute(
        select(UserChallenge).where(
            UserChallenge.user_id == user_id,
            UserChallenge.challenge_type == challenge_type,
            UserChallenge.challenge_ref_id == challenge_ref_id,
        )
    )
    return result.scalar_one_or_none()


async def create_user_challenge(
    db: AsyncSession,
    user_id: UUID,
    challenge_type: str,
    challenge_ref_id: UUID,
    question_id: UUID,
) -> UserChallenge:
    token = generate_solo_room_token(user_id, challenge_type, challenge_ref_id, question_id)
    room_url = build_solo_room_url(challenge_type, challenge_ref_id, token)

    uc = UserChallenge(
        user_id=user_id,
        challenge_type=challenge_type,
        challenge_ref_id=challenge_ref_id,
        status="in_progress",
        started_at=datetime.utcnow(),
        room_token=token,
        room_url=room_url,
    )
    db.add(uc)
    await db.flush()
    return uc
