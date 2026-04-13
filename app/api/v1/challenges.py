"""
1v1 Live Challenges REST API — Part 1.

Endpoints:
  POST   /challenges/matches                    — send invite
  POST   /challenges/matches/{id}/accept        — accept invite
  POST   /challenges/matches/{id}/decline       — decline invite
  GET    /challenges/matches                    — list my matches (with filters)
  GET    /challenges/matches/{id}               — get match detail
  POST   /challenges/matches/{id}/submit        — submit answer
  GET    /challenges/matches/{id}/result        — get match result
  GET    /challenges/elo/me                     — my ELO
  GET    /challenges/elo/{user_id}              — any user's ELO
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.dependencies import get_current_user
from app.models.challenges import Match, ChallengeSubmission, UserElo, ChallengeTask
from app.models.user import User
from app.services.elo_service import get_or_create_elo, STARTING_ELO, _tier_from_elo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/challenges", tags=["challenges"])

INVITE_EXPIRY_HOURS = 24
MAX_PENDING_INVITES = 10


# ── Request schemas ───────────────────────────────────────────────────────────

class SendInviteRequest(BaseModel):
    opponent_id: str
    domain: str = Field("coding", pattern="^coding$")  # 1v1 is coding-only
    duration_minutes: int
    difficulty: str = Field("easy", pattern="^(easy|medium|hard)$")
    invite_message: Optional[str] = Field(None, max_length=200)

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v not in (30, 60, 120):
            raise ValueError("duration_minutes must be 30, 60, or 120")
        return v


class DeclineInviteRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=100)


class RunSampleRequest(BaseModel):
    content: str
    language: Optional[str] = "python"


class SubmitAnswerRequest(BaseModel):
    content: str
    language: Optional[str] = None
    is_auto: bool = False


# Pre-defined decline reasons (returned to frontend for display)
DECLINE_REASONS = [
    "Not available right now",
    "Maybe next time",
    "I'm in a hurry",
    "Not feeling confident",
    "Try me later",
]


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_match(match: Match) -> dict:
    """Serialize a Match ORM object. All relationships must be eagerly loaded."""
    task = match.challenge_task
    question = getattr(match, 'question', None)
    challenger = match.challenger
    opponent = match.opponent

    # Use Question data if available, fall back to ChallengeTask
    task_title = (question.title if question else None) or (task.title if task else None)
    task_description = (question.problem_statement if question else None) or (task.description if task else None)
    task_requirements = (question.constraints if question else None) or (task.requirements if task else None)

    return {
        "id": str(match.id),
        "challenger_id": str(match.challenger_id),
        "opponent_id": str(match.opponent_id),
        "domain": match.domain,
        "task_id": str(match.task_id) if match.task_id else None,
        "question_id": str(match.question_id) if match.question_id else None,
        "duration_minutes": match.duration_minutes,
        "status": match.status,
        "started_at": match.started_at.isoformat() if match.started_at else None,
        "ended_at": match.ended_at.isoformat() if match.ended_at else None,
        "winner_id": str(match.winner_id) if match.winner_id else None,
        "challenger_elo_before": match.challenger_elo_before,
        "opponent_elo_before": match.opponent_elo_before,
        "challenger_elo_after": match.challenger_elo_after,
        "opponent_elo_after": match.opponent_elo_after,
        "created_at": match.created_at.isoformat(),
        "challenger_name": challenger.full_name if challenger else None,
        "opponent_name": opponent.full_name if opponent else None,
        "challenger_avatar_url": challenger.avatar_url if challenger else None,
        "opponent_avatar_url": opponent.avatar_url if opponent else None,
        "task_title": task_title,
        "task_description": task_description,
        "task_requirements": task_requirements,
        # Full question data for the challenge room
        "question": {
            "id": str(question.id),
            "title": question.title,
            "difficulty": question.difficulty,
            "problem_statement": question.problem_statement,
            "constraints": question.constraints,
            "input_format": question.input_format,
            "output_format": question.output_format,
            "sample_input_1": question.sample_input_1,
            "sample_output_1": question.sample_output_1,
            "sample_input_2": question.sample_input_2,
            "sample_output_2": question.sample_output_2,
            "time_limit_ms": question.time_limit_ms,
            "memory_limit_mb": question.memory_limit_mb,
            "tags": question.tags or [],
        } if question else None,
        "invite_message": match.invite_message,
        "decline_reason": match.decline_reason,
        "challenge_link": match.challenge_link,
        "spectator_count": match.spectator_count or 0,
        "difficulty": match.difficulty if hasattr(match, 'difficulty') else "easy",
        "winner_points": match.winner_points or 0,
        "challenge_badge": match.challenge_badge,
    }


def _serialize_submission(sub: ChallengeSubmission) -> dict:
    return {
        "id": str(sub.id),
        "match_id": str(sub.match_id),
        "user_id": str(sub.user_id),
        "content": sub.content,
        "language": sub.language,
        "submitted_at": sub.submitted_at.isoformat(),
        "score": sub.score,
        "score_breakdown": sub.score_breakdown,
        "ai_feedback": sub.ai_feedback,
        "is_auto": sub.is_auto,
    }


def _serialize_elo(elo: UserElo) -> dict:
    # user relationship is selectin-loaded — safe to access
    user = elo.user
    return {
        "user_id": str(elo.user_id),
        "elo": elo.elo,
        "tier": elo.tier,
        "matches_played": elo.matches_played,
        "wins": elo.wins,
        "losses": elo.losses,
        "draws": elo.draws,
        "peak_elo": elo.peak_elo,
        "current_streak": elo.current_streak,
        "updated_at": elo.updated_at.isoformat(),
        "username": user.full_name if user else None,
        "avatar_url": user.avatar_url if user else None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_random_task(db: AsyncSession, domain: str, difficulty: str = "easy") -> Optional[ChallengeTask]:
    from sqlalchemy import func
    result = await db.execute(
        select(ChallengeTask)
        .where(
            ChallengeTask.domain == domain,
            ChallengeTask.difficulty == difficulty,
            ChallengeTask.is_active.is_(True),
        )
        .order_by(func.random())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_random_question(db: AsyncSession, difficulty: str = "easy"):
    """Get a random active Question for the given difficulty."""
    from sqlalchemy import func
    from app.models.challenges import Question
    result = await db.execute(
        select(Question)
        .where(
            Question.difficulty == difficulty,
            Question.is_active.is_(True),
        )
        .order_by(func.random())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _push_challenge_notification(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    body: str,
    data: dict,
    notif_type: str,
) -> None:
    """Create in-app notification only. FCM push is sent separately after commit."""
    from app.services.notification_service import create_notification
    await create_notification(
        db=db,
        user_id=user_id,
        notif_type=notif_type,
        title=title,
        body=body,
        data=data,
    )
    # Schedule FCM push as a fire-and-forget background task (after DB commit)
    try:
        import asyncio
        asyncio.ensure_future(_send_fcm_after_commit(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
            notif_type=notif_type,
        ))
    except Exception as e:
        logger.debug(f"FCM task scheduling failed (non-critical): {e}")


async def _send_fcm_push_background(
    user_id: UUID,
    title: str,
    body: str,
    data: dict,
) -> None:
    """Send FCM push in a fresh DB session. Called as a BackgroundTask after commit."""
    try:
        async with AsyncSessionLocal() as db:
            from backend.notifications.fcm_service import send_push_notification
            await send_push_notification(
                db=db,
                user_id=user_id,
                title=title,
                body=body,
                data=data,
                notif_type=data.get("type", ""),
            )
    except Exception as e:
        logger.warning(f"FCM push failed for {user_id}: {e}")


async def _send_fcm_after_commit(
    user_id: UUID,
    title: str,
    body: str,
    data: dict,
    notif_type: str,
) -> None:
    """Send FCM push in a fresh DB session after the parent transaction commits."""
    # Small delay to ensure the parent transaction has committed
    import asyncio
    await asyncio.sleep(0.5)
    try:
        async with AsyncSessionLocal() as db:
            from backend.notifications.fcm_service import send_push_notification
            await send_push_notification(
                db=db,
                user_id=user_id,
                title=title,
                body=body,
                data=data,
                notif_type=notif_type,
            )
    except Exception as e:
        logger.warning(f"FCM push failed for {user_id}: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/matches", status_code=201)
async def send_invite(
    payload: SendInviteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a 1v1 challenge invite. Max 10 pending invites per user."""
    # Rate limit: max 10 pending invites
    pending_result = await db.execute(
        select(Match).where(
            Match.challenger_id == current_user.id,
            Match.status == "pending",
        )
    )
    if len(pending_result.scalars().all()) >= MAX_PENDING_INVITES:
        raise HTTPException(
            status_code=429,
            detail=f"You have {MAX_PENDING_INVITES} pending invites. Wait for responses before sending more.",
        )

    # Validate opponent
    try:
        opponent_uuid = UUID(payload.opponent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid opponent ID.")

    if opponent_uuid == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot challenge yourself.")

    opp_result = await db.execute(
        select(User).where(User.id == opponent_uuid, User.is_active.is_(True))
    )
    opponent = opp_result.scalar_one_or_none()
    if not opponent:
        raise HTTPException(status_code=404, detail="Opponent not found.")

    # Snapshot ELO at invite time
    c_elo = await get_or_create_elo(db, current_user.id)
    o_elo = await get_or_create_elo(db, opponent_uuid)

    # Auto-assign a random task for the domain and difficulty
    task = await _get_random_task(db, payload.domain, payload.difficulty)

    # Also assign a random Question (coding problem with test cases)
    question = await _get_random_question(db, payload.difficulty)

    match = Match(
        challenger_id=current_user.id,
        opponent_id=opponent_uuid,
        domain=payload.domain,
        difficulty=payload.difficulty,
        task_id=task.id if task else None,
        question_id=question.id if question else None,
        duration_minutes=payload.duration_minutes,
        status="pending",
        challenger_elo_before=c_elo.elo,
        opponent_elo_before=o_elo.elo,
        invite_message=payload.invite_message,
    )
    db.add(match)
    await db.flush()

    # Reload with all relationships
    result = await db.execute(select(Match).where(Match.id == match.id))
    match = result.scalar_one()

    # Create in-app notification (within this transaction)
    try:
        from app.services.notification_service import create_notification
        await create_notification(
            db=db,
            user_id=opponent_uuid,
            notif_type="challenge_invite",
            title=f"{current_user.full_name} challenged you!",
            body=f"{current_user.full_name} challenged you to a 1v1 Coding challenge ({payload.difficulty.title()})",
            data={
                "match_id": str(match.id),
                "type": "challenge_invite",
                "challenger_name": current_user.full_name or "",
                "challenger_avatar": current_user.avatar_url or "",
                "domain": payload.domain,
                "difficulty": payload.difficulty,
                "duration_minutes": str(payload.duration_minutes),
                "invite_message": payload.invite_message or "",
            },
        )
    except Exception as e:
        logger.warning(f"In-app notification failed for match {match.id}: {e}")

    # COMMIT NOW so the match is visible to all DB instances before FCM fires
    await db.commit()

    # Send FCM push AFTER commit via BackgroundTask (runs after response is sent)
    match_id_str = str(match.id)
    fcm_data = {
        "match_id": match_id_str,
        "type": "challenge_invite",
        "challenger_name": current_user.full_name or "",
        "challenger_avatar": current_user.avatar_url or "",
        "domain": payload.domain,
        "difficulty": payload.difficulty,
        "duration_minutes": str(payload.duration_minutes),
        "invite_message": payload.invite_message or "",
    }
    background_tasks.add_task(
        _send_fcm_push_background,
        user_id=opponent_uuid,
        title=f"{current_user.full_name} challenged you!",
        body=f"{current_user.full_name} challenged you to a 1v1 Coding challenge ({payload.difficulty.title()})",
        data=fcm_data,
    )

    # Schedule expiry (non-blocking background task)
    background_tasks.add_task(_expire_match_after_24h, match_id_str)

    return _serialize_match(match)


@router.post("/matches/{match_id}/accept")
async def accept_invite(
    match_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the opponent can accept this invite.")
    if match.status != "pending":
        raise HTTPException(status_code=400, detail=f"Match is already {match.status}.")

    # Check expiry
    if datetime.utcnow() > match.created_at + timedelta(hours=INVITE_EXPIRY_HOURS):
        match.status = "expired"
        await db.flush()
        raise HTTPException(status_code=400, detail="This invite has expired.")

    match.status = "active"
    match.started_at = datetime.utcnow()
    await db.flush()

    # Generate and persist the external challenge room link
    from app.services.challenge_link_service import generate_challenge_link_for_user
    # Generate user-specific links so each user's token has their user_id
    challenger_link = generate_challenge_link_for_user(match.id, match.challenger_id)
    opponent_link = generate_challenge_link_for_user(match.id, match.opponent_id)
    # Store the challenger's link as the canonical challenge_link (for backwards compat)
    match.challenge_link = challenger_link
    challenge_link = challenger_link
    challenger_id = match.challenger_id
    opponent_id = match.opponent_id
    duration_minutes = match.duration_minutes
    await db.flush()

    # Create in-app notifications within this transaction
    try:
        from app.services.notification_service import create_notification
        await create_notification(
            db=db,
            user_id=challenger_id,
            notif_type="challenge_accepted",
            title="Challenge accepted! 🎯",
            body=f"{current_user.full_name} accepted your challenge. Get ready!",
            data={"match_id": str(match_id), "type": "challenge_accepted", "challenge_link": challenger_link},
        )
        for uid, link in [(challenger_id, challenger_link), (opponent_id, opponent_link)]:
            await create_notification(
                db=db,
                user_id=uid,
                notif_type="match_starting",
                title="⚡ Match starting now!",
                body="Your 1v1 challenge is live. Open the challenge room!",
                data={"match_id": str(match_id), "type": "match_starting", "challenge_link": link},
            )
    except Exception as e:
        logger.warning(f"Accept in-app notification failed: {e}")

    # COMMIT NOW so the match is visible before FCM fires
    await db.commit()

    # Send FCM pushes AFTER commit via BackgroundTasks
    background_tasks.add_task(
        _send_fcm_push_background,
        user_id=challenger_id,
        title="Challenge accepted! 🎯",
        body=f"{current_user.full_name} accepted your challenge. Get ready!",
        data={"match_id": str(match_id), "type": "challenge_accepted", "challenge_link": challenger_link},
    )
    for uid, link in [(challenger_id, challenger_link), (opponent_id, opponent_link)]:
        background_tasks.add_task(
            _send_fcm_push_background,
            user_id=uid,
            title="⚡ Match starting now!",
            body="Your 1v1 challenge is live. Open the challenge room!",
            data={"match_id": str(match_id), "type": "match_starting", "challenge_link": link},
        )

    # Broadcast timer_start via WebSocket (non-blocking)
    background_tasks.add_task(
        _broadcast_match_start, str(match_id), duration_minutes
    )

    # Reload with relationships
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one()
    return _serialize_match(match)


@router.get("/decline-reasons")
async def get_decline_reasons() -> list[str]:
    """Return pre-defined decline reasons for the UI."""
    return DECLINE_REASONS


@router.post("/matches/{match_id}/decline")
async def decline_invite(
    match_id: UUID,
    payload: DeclineInviteRequest = DeclineInviteRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the opponent can decline this invite.")
    if match.status != "pending":
        raise HTTPException(status_code=400, detail=f"Match is already {match.status}.")

    match.status = "cancelled"
    match.decline_reason = payload.reason
    await db.flush()

    reason_text = payload.reason or "Not available right now"
    try:
        await _push_challenge_notification(
            db=db,
            user_id=match.challenger_id,
            title="Challenge declined",
            body=f"{current_user.full_name} declined your challenge: \"{reason_text}\"",
            data={
                "match_id": str(match_id),
                "type": "challenge_declined",
                "opponent_name": current_user.full_name or "Opponent",
                "decline_reason": reason_text,
            },
            notif_type="challenge_declined",
        )
    except Exception as e:
        logger.warning(f"Decline notification failed: {e}")

    return {"status": "declined", "reason": reason_text}


@router.post("/matches/{match_id}/cancel")
async def cancel_invite(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Challenger cancels their own pending invite."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.challenger_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the challenger can cancel this invite.")
    if match.status != "pending":
        raise HTTPException(status_code=400, detail=f"Match is already {match.status}.")

    match.status = "cancelled"
    await db.flush()

    # Notify opponent
    try:
        opp_result = await db.execute(select(User).where(User.id == match.opponent_id))
        opp = opp_result.scalar_one_or_none()
        opp_name = opp.full_name if opp else "Opponent"
        await _push_challenge_notification(
            db=db,
            user_id=match.opponent_id,
            title="Challenge cancelled",
            body=f"{current_user.full_name} cancelled their challenge invite.",
            data={"match_id": str(match_id), "type": "challenge_cancelled"},
            notif_type="challenge_cancelled",
        )
    except Exception as e:
        logger.warning(f"Cancel notification failed: {e}")

    return {"status": "cancelled"}


@router.get("/matches/{match_id}/room-token")
async def get_room_token(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a fresh challenge room URL/token for an active match."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.challenger_id != current_user.id and match.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not a participant in this match.")
    if match.status not in ("active", "pending"):
        raise HTTPException(status_code=400, detail=f"Match is {match.status}.")

    from app.services.challenge_link_service import generate_challenge_link
    room_url = match.challenge_link or generate_challenge_link(match.id)
    return {"room_url": room_url, "match_id": str(match_id)}


@router.get("/matches")
async def list_my_matches(
    domain: Optional[str] = Query(None),
    result: Optional[str] = Query(None, pattern="^(win|loss|draw)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    filters = [
        or_(
            Match.challenger_id == current_user.id,
            Match.opponent_id == current_user.id,
        )
    ]

    if domain:
        filters.append(Match.domain == domain)

    if from_date:
        try:
            filters.append(Match.created_at >= datetime.fromisoformat(from_date))
        except ValueError:
            pass

    if to_date:
        try:
            filters.append(Match.created_at <= datetime.fromisoformat(to_date))
        except ValueError:
            pass

    stmt = (
        select(Match)
        .where(and_(*filters))
        .order_by(Match.created_at.desc())
        .limit(limit)
    )
    matches_result = await db.execute(stmt)
    matches = list(matches_result.scalars().all())

    # Post-filter by result (requires per-user perspective)
    if result:
        filtered = []
        for m in matches:
            if m.status != "completed":
                continue
            winner = m.winner_id
            if result == "draw" and winner is None:
                filtered.append(m)
            elif result == "win" and winner == current_user.id:
                filtered.append(m)
            elif result == "loss" and winner is not None and winner != current_user.id:
                filtered.append(m)
        matches = filtered

    return [_serialize_match(m) for m in matches]


@router.get("/matches/{match_id}")
async def get_match(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    import asyncio as _asyncio
    # Retry up to 6 times with increasing delay to handle multi-instance read-after-write lag
    delays = [0.3, 0.6, 1.0, 1.5, 2.0, 2.5]
    for attempt, delay in enumerate(delays):
        db.expire_all()  # clear session cache so we always hit the DB
        result = await db.execute(select(Match).where(Match.id == match_id))
        match = result.scalar_one_or_none()
        if match:
            # Verify the requesting user is a participant or the match is accessible
            if match.challenger_id != current_user.id and match.opponent_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not a participant.")
            return _serialize_match(match)
        if attempt < len(delays) - 1:
            await _asyncio.sleep(delay)
    raise HTTPException(status_code=404, detail="Match not found.")


@router.get("/room/{match_id}")
async def get_room_match(
    match_id: UUID,
    token: str = Query(..., description="Challenge room JWT"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Public endpoint for the challenge room web app.
    Authenticated via the challenge JWT (not Firebase).
    Returns match + task data needed to render the room.
    """
    from app.services.challenge_link_service import verify_challenge_token
    from jose import JWTError
    try:
        payload = verify_challenge_token(token)
        token_match_id = payload.get("match_id")
        if str(match_id) != token_match_id:
            raise HTTPException(status_code=403, detail="Token does not match match ID.")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired challenge token.")

    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")

    return _serialize_match(match)


@router.post("/room/{match_id}/submit")
async def room_submit_answer(
    match_id: UUID,
    payload: SubmitAnswerRequest,
    token: str = Query(..., description="Challenge room JWT"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Submit answer from the challenge room web app.
    Authenticated via challenge JWT. Identifies the submitter from the token's match_id
    and the user_id embedded in the token (set at accept time).
    """
    from app.services.challenge_link_service import verify_challenge_token
    from jose import JWTError
    try:
        token_payload = verify_challenge_token(token)
        token_match_id = token_payload.get("match_id")
        if str(match_id) != token_match_id:
            raise HTTPException(status_code=403, detail="Token does not match match ID.")
        user_id_str = token_payload.get("user_id")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Token missing user_id.")
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired challenge token.")

    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.challenger_id != user_id and match.opponent_id != user_id:
        raise HTTPException(status_code=403, detail="Not a participant.")
    if match.status != "active":
        raise HTTPException(status_code=400, detail=f"Match is {match.status}.")

    # Check for existing submission
    existing = await db.execute(
        select(ChallengeSubmission).where(
            ChallengeSubmission.match_id == match_id,
            ChallengeSubmission.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already submitted.")

    submission = ChallengeSubmission(
        match_id=match_id,
        user_id=user_id,
        content=payload.content,
        language=payload.language,
        is_auto=payload.is_auto,
    )
    db.add(submission)
    await db.flush()
    await db.commit()

    # Trigger evaluation in background
    background_tasks.add_task(_evaluate_now, str(match_id))

    return {
        "id": str(submission.id),
        "match_id": str(match_id),
        "user_id": str(user_id),
        "submitted_at": submission.submitted_at.isoformat(),
    }


@router.post("/matches/{match_id}/run")
async def run_sample_tests(
    match_id: UUID,
    payload: RunSampleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Execute code against sample test cases only (not hidden suite).
    Returns pass/fail per sample test. No score impact.
    """
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.challenger_id != current_user.id and match.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not a participant.")

    # Get task for sample I/O
    task = match.challenge_task
    if not task:
        return [{"status": "no_task", "stdout": "", "stderr": "No task assigned.", "passed": False}]

    from app.services.challenge_evaluation_service import LANGUAGE_IDS, JUDGE0_URL, JUDGE0_HEADERS
    import httpx

    lang_id = LANGUAGE_IDS.get(payload.language or "python", 71)
    api_key = getattr(__import__('app.core.config', fromlist=['settings']).settings, 'judge0_api_key', '')

    # Build sample test cases from task fields
    samples = []
    if hasattr(task, 'sample_input_1') and task.sample_input_1:
        samples.append({
            "input": task.sample_input_1,
            "expected": getattr(task, 'sample_output_1', '') or '',
        })
    if hasattr(task, 'sample_input_2') and task.sample_input_2:
        samples.append({
            "input": task.sample_input_2,
            "expected": getattr(task, 'sample_output_2', '') or '',
        })

    # Fallback: use description as context, run without I/O check
    if not samples:
        return [{"status": "no_samples", "stdout": "No sample test cases available for this task.", "stderr": "", "passed": True}]

    if not api_key:
        # No Judge0 key — return mock pass
        return [{"status": "accepted", "stdout": "Sample test passed (mock).", "stderr": "", "passed": True} for _ in samples]

    results = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for sample in samples:
                resp = await client.post(
                    f"{JUDGE0_URL}/submissions",
                    headers=JUDGE0_HEADERS,
                    json={
                        "source_code": payload.content,
                        "language_id": lang_id,
                        "stdin": sample["input"],
                        "expected_output": sample["expected"],
                        "cpu_time_limit": 5,
                        "memory_limit": 256000,
                    },
                    params={"base64_encoded": "false", "wait": "true"},
                )
                data = resp.json()
                status_id = data.get("status", {}).get("id", 0)
                passed = status_id == 3  # Accepted
                results.append({
                    "status": data.get("status", {}).get("description", "Unknown"),
                    "stdout": (data.get("stdout") or "")[:500],
                    "stderr": (data.get("stderr") or data.get("compile_output") or "")[:300],
                    "passed": passed,
                })
    except Exception as e:
        logger.warning(f"Judge0 run failed: {e}")
        results = [{"status": "error", "stdout": "", "stderr": str(e)[:200], "passed": False}]

    return results


@router.post("/matches/{match_id}/submit")
async def submit_answer(
    match_id: UUID,
    payload: SubmitAnswerRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.challenger_id != current_user.id and match.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not a participant in this match.")
    if match.status not in ("active", "pending"):
        raise HTTPException(status_code=400, detail=f"Match is {match.status}. Cannot submit.")

    # Prevent duplicate submission
    existing = await db.execute(
        select(ChallengeSubmission).where(
            ChallengeSubmission.match_id == match_id,
            ChallengeSubmission.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already submitted for this match.")

    submission = ChallengeSubmission(
        match_id=match_id,
        user_id=current_user.id,
        content=payload.content,
        language=payload.language,
        is_auto=payload.is_auto,
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)

    # Broadcast opponent_submitted status to the other player via WS
    background_tasks.add_task(
        _broadcast_opponent_submitted, str(match_id), str(current_user.id)
    )

    # Count total submissions — if both submitted, trigger evaluation immediately
    subs_result = await db.execute(
        select(ChallengeSubmission).where(ChallengeSubmission.match_id == match_id)
    )
    all_subs = subs_result.scalars().all()
    if len(all_subs) >= 2:
        # Both submitted — cancel timer and evaluate now
        background_tasks.add_task(_evaluate_now, str(match_id))

    return _serialize_submission(submission)


@router.get("/matches/{match_id}/result")
async def get_match_result(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.status != "completed":
        raise HTTPException(
            status_code=404,
            detail="Match result not ready yet. Evaluation is in progress.",
        )

    # Fetch submissions
    subs_result = await db.execute(
        select(ChallengeSubmission).where(ChallengeSubmission.match_id == match_id)
    )
    submissions = subs_result.scalars().all()

    my_sub = next((s for s in submissions if s.user_id == current_user.id), None)
    opp_id = (
        match.opponent_id
        if match.challenger_id == current_user.id
        else match.challenger_id
    )
    opp_sub = next((s for s in submissions if s.user_id == opp_id), None)

    # ELO perspective
    is_challenger = match.challenger_id == current_user.id
    my_elo_before = match.challenger_elo_before if is_challenger else match.opponent_elo_before
    my_elo_after = match.challenger_elo_after if is_challenger else match.opponent_elo_after
    opp_elo_before = match.opponent_elo_before if is_challenger else match.challenger_elo_before
    opp_elo_after = match.opponent_elo_after if is_challenger else match.challenger_elo_after

    my_elo_change = (my_elo_after - my_elo_before) if my_elo_after is not None else 0
    opp_elo_change = (opp_elo_after - opp_elo_before) if opp_elo_after is not None else 0

    my_new_tier = _tier_from_elo(my_elo_after if my_elo_after is not None else my_elo_before)
    opp_new_tier = _tier_from_elo(opp_elo_after if opp_elo_after is not None else opp_elo_before)
    my_old_tier = _tier_from_elo(my_elo_before)
    tier_changed = my_new_tier != my_old_tier

    # Opponent submission: score is public, content/feedback is private
    opp_sub_dict = None
    if opp_sub:
        opp_sub_dict = {
            "id": str(opp_sub.id),
            "match_id": str(opp_sub.match_id),
            "user_id": str(opp_sub.user_id),
            "content": "",          # private
            "language": opp_sub.language,
            "submitted_at": opp_sub.submitted_at.isoformat(),
            "score": opp_sub.score,
            "score_breakdown": None,  # private
            "ai_feedback": None,      # private
            "is_auto": opp_sub.is_auto,
        }

    return {
        "match": _serialize_match(match),
        "my_submission": _serialize_submission(my_sub) if my_sub else None,
        "opponent_submission": opp_sub_dict,
        "my_elo_change": my_elo_change,
        "opponent_elo_change": opp_elo_change,
        "my_new_elo": my_elo_after if my_elo_after is not None else my_elo_before,
        "opponent_new_elo": opp_elo_after if opp_elo_after is not None else opp_elo_before,
        "my_new_tier": my_new_tier,
        "opponent_new_tier": opp_new_tier,
        "tier_changed": tier_changed,
    }


@router.get("/elo/me")
async def get_my_elo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    elo = await get_or_create_elo(db, current_user.id)
    return _serialize_elo(elo)


@router.get("/elo/{user_id}")
async def get_user_elo(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(UserElo).where(UserElo.user_id == user_id))
    elo = result.scalar_one_or_none()
    if not elo:
        return {
            "user_id": str(user_id),
            "elo": STARTING_ELO,
            "tier": "silver",
            "matches_played": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "peak_elo": STARTING_ELO,
            "current_streak": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "username": None,
            "avatar_url": None,
        }
    return _serialize_elo(elo)


# ── Background task helpers ───────────────────────────────────────────────────

async def _expire_match_after_24h(match_id: str) -> None:
    """
    Auto-expire a pending invite after 24 hours.
    Uses asyncio.sleep — only survives for the lifetime of the server process.
    For production, use a Celery beat task or pg_cron instead.
    """
    await asyncio.sleep(INVITE_EXPIRY_HOURS * 3600)
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Match).where(Match.id == UUID(match_id))
            )
            match = result.scalar_one_or_none()
            if match and match.status == "pending":
                match.status = "expired"
                # Notify challenger
                opp_result = await db.execute(
                    select(User).where(User.id == match.opponent_id)
                )
                opp = opp_result.scalar_one_or_none()
                opp_name = opp.full_name if opp else "Opponent"
                await _push_challenge_notification(
                    db=db,
                    user_id=match.challenger_id,
                    title="Challenge invite expired",
                    body=f"Your challenge invite to {opp_name} expired.",
                    data={"match_id": match_id, "type": "invite_expired"},
                    notif_type="invite_expired",
                )
                await db.commit()
    except Exception as e:
        logger.error(f"Expiry task failed for {match_id}: {e}")


async def _broadcast_match_start(match_id: str, duration_minutes: int) -> None:
    """Broadcast timer_start to all WebSocket connections in the room."""
    try:
        from app.api.v1.challenges_ws import broadcast_to_room
        remaining = duration_minutes * 60
        await broadcast_to_room(match_id, "timer_start", {"remaining_seconds": remaining})
    except Exception as e:
        logger.warning(f"Broadcast match start failed: {e}")


async def _broadcast_opponent_submitted(match_id: str, submitter_id: str) -> None:
    """Broadcast opponent_status=submitted to the other player's WS connection."""
    try:
        from app.api.v1.challenges_ws import _rooms, _send
        for ws, uid, is_spec in list(_rooms.get(match_id, set())):
            if uid != submitter_id and not is_spec:
                await _send(ws, "opponent_status", {"status": "submitted"})
    except Exception as e:
        logger.warning(f"Broadcast opponent submitted failed: {e}")


async def _evaluate_now(match_id: str) -> None:
    """
    Trigger evaluation immediately (both players submitted).
    Cancels the WS timer task if running.
    """
    try:
        from app.api.v1.challenges_ws import _timer_tasks, _trigger_evaluation
        task = _timer_tasks.pop(match_id, None)
        if task and not task.done():
            task.cancel()
        await _trigger_evaluation(match_id)
    except Exception as e:
        logger.error(f"Immediate evaluation failed for {match_id}: {e}")


@router.get("/matches/{match_id}/compare")
async def get_match_compare(
    match_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns side-by-side comparison data for both players.
    Available once match.status == 'completed'.
    Both players can call this; opponent's ai_feedback is hidden.
    """
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.status != "completed":
        raise HTTPException(status_code=404, detail="Match not completed yet.")

    subs_result = await db.execute(
        select(ChallengeSubmission).where(ChallengeSubmission.match_id == match_id)
    )
    submissions = subs_result.scalars().all()

    is_challenger = match.challenger_id == current_user.id
    my_id = current_user.id
    opp_id = match.opponent_id if is_challenger else match.challenger_id

    my_sub = next((s for s in submissions if s.user_id == my_id), None)
    opp_sub = next((s for s in submissions if s.user_id == opp_id), None)

    my_elo_before = match.challenger_elo_before if is_challenger else match.opponent_elo_before
    my_elo_after = match.challenger_elo_after if is_challenger else match.opponent_elo_after
    opp_elo_before = match.opponent_elo_before if is_challenger else match.challenger_elo_before
    opp_elo_after = match.opponent_elo_after if is_challenger else match.challenger_elo_after

    def _sub_public(sub: ChallengeSubmission | None, is_me: bool) -> dict | None:
        if not sub:
            return None
        return {
            "user_id": str(sub.user_id),
            "score": sub.score,
            "time_taken_seconds": int(
                (sub.submitted_at - match.started_at).total_seconds()
            ) if match.started_at else None,
            "is_auto": sub.is_auto,
            "language": sub.language,
            "score_breakdown": sub.score_breakdown if is_me else None,
            "ai_feedback": sub.ai_feedback if is_me else None,
        }

    return {
        "match": _serialize_match(match),
        "my_result": _sub_public(my_sub, True),
        "opponent_result": _sub_public(opp_sub, False),
        "winner_id": str(match.winner_id) if match.winner_id else None,
        "is_draw": match.winner_id is None,
        "my_elo_change": (my_elo_after - my_elo_before) if my_elo_after is not None else 0,
        "opponent_elo_change": (opp_elo_after - opp_elo_before) if opp_elo_after is not None else 0,
        "my_new_elo": my_elo_after if my_elo_after is not None else my_elo_before,
        "opponent_new_elo": opp_elo_after if opp_elo_after is not None else opp_elo_before,
        "my_new_tier": _tier_from_elo(my_elo_after if my_elo_after is not None else my_elo_before),
        "opponent_new_tier": _tier_from_elo(opp_elo_after if opp_elo_after is not None else opp_elo_before),
    }
