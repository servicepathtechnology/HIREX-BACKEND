"""Streak evaluation service — Part 2."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.solo_challenges import UserStreak, StreakHistory

logger = logging.getLogger(__name__)

# Streak milestone definitions: (days, badge_name, xp)
STREAK_MILESTONES = [
    (3,   "warming_up",       20),
    (7,   "on_fire",          50),
    (14,  "unstoppable",     100),
    (30,  "streak_champion", 200),
    (60,  "coding_machine",  500),
    (100, "legend",         1000),
]


async def get_or_create_streak(db: AsyncSession, user_id: UUID) -> UserStreak:
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
    streak = result.scalar_one_or_none()
    if not streak:
        streak = UserStreak(user_id=user_id)
        db.add(streak)
        await db.flush()
    return streak


async def record_daily_attempt(
    db: AsyncSession,
    user_id: UUID,
    attempt_date: date,
) -> UserStreak:
    """
    Called when a user opens/attempts the daily challenge.
    Updates streak and logs the event.
    """
    streak = await get_or_create_streak(db, user_id)
    today = attempt_date

    # Already recorded today — idempotent
    if streak.last_activity_date == today:
        return streak

    yesterday = today - timedelta(days=1)

    if streak.last_activity_date is None:
        # First ever attempt
        streak.current_streak = 1
        streak.streak_started_date = today
    elif streak.last_activity_date == yesterday:
        # Consecutive day
        streak.current_streak += 1
    elif streak.grace_day_used_date == yesterday and streak.last_activity_date == today - timedelta(days=2):
        # Grace day was used yesterday, user is back today — streak continues
        streak.current_streak += 1
    else:
        # Gap > 1 day (or grace already used) — reset
        streak.current_streak = 1
        streak.streak_started_date = today
        streak.grace_day_available = True
        streak.grace_day_used_date = None

    streak.last_activity_date = today
    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    # Replenish grace day every 7 consecutive days
    if streak.current_streak % 7 == 0:
        streak.grace_day_available = True

    await db.flush()

    # Log event
    db.add(StreakHistory(
        user_id=user_id,
        event_date=today,
        event_type="attempted",
        streak_count=streak.current_streak,
    ))
    await db.flush()

    return streak


async def evaluate_missed_day(
    db: AsyncSession,
    user_id: UUID,
    today: date,
) -> tuple[UserStreak, str]:
    """
    Called by the nightly cron for users who did NOT attempt yesterday.
    Returns (streak, action) where action is 'grace_applied' | 'streak_broken' | 'no_change'.
    """
    streak = await get_or_create_streak(db, user_id)
    yesterday = today - timedelta(days=1)

    if streak.last_activity_date is None or streak.current_streak == 0:
        return streak, "no_change"

    if streak.last_activity_date >= yesterday:
        # Already active — no miss
        return streak, "no_change"

    # User missed yesterday
    if streak.grace_day_available and streak.grace_day_used_date != yesterday:
        # Apply grace day
        streak.grace_day_available = False
        streak.grace_day_used_date = yesterday
        await db.flush()
        db.add(StreakHistory(
            user_id=user_id,
            event_date=yesterday,
            event_type="grace_used",
            streak_count=streak.current_streak,
        ))
        await db.flush()
        return streak, "grace_applied"
    else:
        # Break streak
        old_streak = streak.current_streak
        streak.current_streak = 0
        streak.grace_day_available = True
        streak.grace_day_used_date = None
        streak.streak_started_date = None
        await db.flush()
        db.add(StreakHistory(
            user_id=user_id,
            event_date=yesterday,
            event_type="streak_broken",
            streak_count=old_streak,
        ))
        await db.flush()
        return streak, "streak_broken"


async def check_and_award_milestones(
    db: AsyncSession,
    user_id: UUID,
    current_streak: int,
) -> list[tuple[int, str, int]]:
    """
    Check if the current streak hits any milestone.
    Returns list of (days, badge_name, xp) for newly hit milestones.
    """
    from app.models.user import User
    newly_hit = []
    for days, badge_name, xp in STREAK_MILESTONES:
        if current_streak == days:
            newly_hit.append((days, badge_name, xp))
            # Award XP
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.xp_points = (user.xp_points or 0) + xp
                await db.flush()
            # Log milestone event
            db.add(StreakHistory(
                user_id=user_id,
                event_date=date.today(),
                event_type="milestone",
                streak_count=current_streak,
            ))
            await db.flush()
    return newly_hit
