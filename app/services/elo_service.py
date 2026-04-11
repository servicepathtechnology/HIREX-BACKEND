"""ELO calculation and update service for 1v1 Live Challenges."""

from __future__ import annotations

import math
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.challenges import UserElo


K_FACTOR = 32
STARTING_ELO = 1000
DRAW_THRESHOLD = 2  # scores within 2 pts = draw


def _tier_from_elo(elo: int) -> str:
    if elo >= 1800:
        return "elite"
    if elo >= 1600:
        return "diamond"
    if elo >= 1400:
        return "platinum"
    if elo >= 1200:
        return "gold"
    if elo >= 1000:
        return "silver"
    return "bronze"


def _expected_score(elo_a: int, elo_b: int) -> float:
    return 1.0 / (1.0 + math.pow(10, (elo_b - elo_a) / 400.0))


def calculate_elo(
    elo_a: int,
    elo_b: int,
    score_a: Optional[int],
    score_b: Optional[int],
) -> tuple[int, int]:
    """
    Returns (new_elo_a, new_elo_b).
    Actual score: Win=1.0, Loss=0.0, Draw=0.5
    """
    # Determine actual scores
    if score_a is not None and score_b is None:
        actual_a, actual_b = 1.0, 0.0
    elif score_a is None and score_b is not None:
        actual_a, actual_b = 0.0, 1.0
    elif score_a is None and score_b is None:
        actual_a, actual_b = 0.5, 0.5
    else:
        diff = abs(score_a - score_b)  # type: ignore[operator]
        if diff <= DRAW_THRESHOLD:
            actual_a, actual_b = 0.5, 0.5
        elif score_a > score_b:  # type: ignore[operator]
            actual_a, actual_b = 1.0, 0.0
        else:
            actual_a, actual_b = 0.0, 1.0

    exp_a = _expected_score(elo_a, elo_b)
    exp_b = _expected_score(elo_b, elo_a)

    new_a = round(elo_a + K_FACTOR * (actual_a - exp_a))
    new_b = round(elo_b + K_FACTOR * (actual_b - exp_b))

    return max(0, min(9999, new_a)), max(0, min(9999, new_b))


async def get_or_create_elo(db: AsyncSession, user_id) -> UserElo:
    result = await db.execute(select(UserElo).where(UserElo.user_id == user_id))
    elo_record = result.scalar_one_or_none()
    if not elo_record:
        elo_record = UserElo(user_id=user_id, elo=STARTING_ELO, tier="silver")
        db.add(elo_record)
        await db.flush()
    return elo_record


async def apply_elo_update(
    db: AsyncSession,
    challenger_id,
    opponent_id,
    score_challenger: Optional[int],
    score_opponent: Optional[int],
) -> tuple[UserElo, UserElo, bool, bool]:
    """
    Calculates and persists ELO changes for both players.
    Returns (challenger_elo, opponent_elo, challenger_tier_changed, opponent_tier_changed).
    """
    c_elo = await get_or_create_elo(db, challenger_id)
    o_elo = await get_or_create_elo(db, opponent_id)

    old_c_tier = c_elo.tier
    old_o_tier = o_elo.tier

    new_c, new_o = calculate_elo(c_elo.elo, o_elo.elo, score_challenger, score_opponent)

    # Determine result for stats
    if score_challenger is not None and score_opponent is None:
        c_result, o_result = "win", "loss"
    elif score_challenger is None and score_opponent is not None:
        c_result, o_result = "loss", "win"
    elif score_challenger is None and score_opponent is None:
        c_result, o_result = "draw", "draw"
    else:
        diff = abs(score_challenger - score_opponent)  # type: ignore[operator]
        if diff <= DRAW_THRESHOLD:
            c_result, o_result = "draw", "draw"
        elif score_challenger > score_opponent:  # type: ignore[operator]
            c_result, o_result = "win", "loss"
        else:
            c_result, o_result = "loss", "win"

    # Update challenger
    c_elo.elo = new_c
    c_elo.tier = _tier_from_elo(new_c)
    c_elo.matches_played += 1
    c_elo.peak_elo = max(c_elo.peak_elo, new_c)
    if c_result == "win":
        c_elo.wins += 1
        c_elo.current_streak = max(0, c_elo.current_streak) + 1
    elif c_result == "loss":
        c_elo.losses += 1
        c_elo.current_streak = min(0, c_elo.current_streak) - 1
    else:
        c_elo.draws += 1
        c_elo.current_streak = 0

    # Update opponent
    o_elo.elo = new_o
    o_elo.tier = _tier_from_elo(new_o)
    o_elo.matches_played += 1
    o_elo.peak_elo = max(o_elo.peak_elo, new_o)
    if o_result == "win":
        o_elo.wins += 1
        o_elo.current_streak = max(0, o_elo.current_streak) + 1
    elif o_result == "loss":
        o_elo.losses += 1
        o_elo.current_streak = min(0, o_elo.current_streak) - 1
    else:
        o_elo.draws += 1
        o_elo.current_streak = 0

    await db.flush()

    c_tier_changed = c_elo.tier != old_c_tier
    o_tier_changed = o_elo.tier != old_o_tier

    return c_elo, o_elo, c_tier_changed, o_tier_changed
