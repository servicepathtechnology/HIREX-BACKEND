"""Challenge-specific notification helpers."""

from __future__ import annotations

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.notification_service import create_notification


async def notify_challenge_invite(
    db: AsyncSession,
    opponent_id: UUID,
    challenger_name: str,
    domain: str,
    match_id: str,
) -> None:
    await create_notification(
        db=db,
        user_id=opponent_id,
        notif_type="challenge_invite",
        title=f"{challenger_name} challenged you!",
        body=f"{challenger_name} challenged you to a 1v1 in {domain.title()}",
        data={"match_id": match_id, "type": "challenge_invite"},
    )


async def notify_challenge_accepted(
    db: AsyncSession,
    challenger_id: UUID,
    opponent_name: str,
    match_id: str,
) -> None:
    await create_notification(
        db=db,
        user_id=challenger_id,
        notif_type="challenge_accepted",
        title="Challenge accepted!",
        body=f"{opponent_name} accepted your challenge. Get ready!",
        data={"match_id": match_id, "type": "challenge_accepted"},
    )


async def notify_challenge_declined(
    db: AsyncSession,
    challenger_id: UUID,
    opponent_name: str,
    match_id: str,
) -> None:
    await create_notification(
        db=db,
        user_id=challenger_id,
        notif_type="challenge_declined",
        title="Challenge declined",
        body=f"{opponent_name} declined your challenge.",
        data={"match_id": match_id, "type": "challenge_declined"},
    )


async def notify_match_starting(
    db: AsyncSession,
    user_id: UUID,
    match_id: str,
) -> None:
    await create_notification(
        db=db,
        user_id=user_id,
        notif_type="match_starting",
        title="Match starting in 60 seconds!",
        body="Your match starts in 60 seconds. Head to the room!",
        data={"match_id": match_id, "type": "match_starting"},
    )


async def notify_match_result_ready(
    db: AsyncSession,
    user_id: UUID,
    match_id: str,
) -> None:
    await create_notification(
        db=db,
        user_id=user_id,
        notif_type="match_result_ready",
        title="Match result ready!",
        body="Your match result is ready. See how you did.",
        data={"match_id": match_id, "type": "match_result_ready"},
    )


async def notify_elo_tier_changed(
    db: AsyncSession,
    user_id: UUID,
    new_tier: str,
    new_elo: int,
) -> None:
    tier_display = new_tier.title()
    await create_notification(
        db=db,
        user_id=user_id,
        notif_type="elo_tier_changed",
        title=f"You've reached {tier_display}!",
        body=f"Congratulations! You've reached {tier_display} tier with {new_elo} ELO!",
        data={"tier": new_tier, "elo": new_elo, "type": "elo_tier_changed"},
    )


async def notify_invite_expired(
    db: AsyncSession,
    challenger_id: UUID,
    opponent_name: str,
    match_id: str,
) -> None:
    await create_notification(
        db=db,
        user_id=challenger_id,
        notif_type="invite_expired",
        title="Challenge invite expired",
        body=f"Your challenge invite to {opponent_name} expired.",
        data={"match_id": match_id, "type": "invite_expired"},
    )


_BADGE_DISPLAY = {
    "coding_warrior": ("🏅 Coding Warrior", "You won an Easy 1v1 challenge!"),
    "code_crusher":   ("💪 Code Crusher",   "You won a Medium 1v1 challenge!"),
    "algorithm_master": ("🧠 Algorithm Master", "You won a Hard 1v1 challenge!"),
}


async def notify_challenge_badge_earned(
    db: AsyncSession,
    user_id: UUID,
    badge_slug: str,
    match_id: str,
) -> None:
    title, body = _BADGE_DISPLAY.get(badge_slug, ("🏆 Badge Earned!", "You earned a new badge!"))
    await create_notification(
        db=db,
        user_id=user_id,
        notif_type="challenge_badge_earned",
        title=title,
        body=body,
        data={"badge": badge_slug, "match_id": match_id, "type": "challenge_badge_earned"},
    )
