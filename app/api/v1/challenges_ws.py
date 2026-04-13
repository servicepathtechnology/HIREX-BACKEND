"""
WebSocket handler for 1v1 Live Challenge rooms.

Route: /ws/challenges/{match_id}?token=<firebase_token>

Events sent to clients:
  connection_status — {connected: bool}
  timer_start       — {remaining_seconds: int}
  timer_tick        — {remaining_seconds: int}  (every 5s)
  opponent_status   — {status: "waiting"|"working"|"submitted"}
  match_completed   — {match_id: str}
  spectator_count   — {count: int}

Events received from clients:
  status_update     — {type: "status_update", status: "working"|"submitted"}
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Set
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.database import AsyncSessionLocal
from app.core.dependencies import verify_token
from app.models.challenges import Match

logger = logging.getLogger(__name__)

ws_challenges_router = APIRouter(tags=["challenges-ws"])

# ── Connection registry ───────────────────────────────────────────────────────
# match_id -> set of (websocket, user_id, is_spectator)
_rooms: Dict[str, Set[tuple]] = defaultdict(set)

# Active server-side timer tasks per match
_timer_tasks: Dict[str, asyncio.Task] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send(ws: WebSocket, event_type: str, data: dict) -> None:
    """Send a JSON event to a single WebSocket, silently ignoring errors."""
    try:
        await ws.send_text(json.dumps({"type": event_type, "data": data}))
    except Exception:
        pass


async def broadcast_to_room(match_id: str, event_type: str, data: dict) -> None:
    """Broadcast an event to every connection in a room."""
    for ws, _, _ in list(_rooms.get(match_id, set())):
        await _send(ws, event_type, data)


async def broadcast_match_completed(match_id: str) -> None:
    """Called by the evaluation service after match is completed."""
    await broadcast_to_room(match_id, "match_completed", {"match_id": match_id})


async def _broadcast_spectator_count(match_id: str) -> None:
    spectators = sum(1 for _, _, is_spec in _rooms.get(match_id, set()) if is_spec)
    await broadcast_to_room(match_id, "spectator_count", {"count": spectators})


async def _trigger_evaluation(match_id: str) -> None:
    """Trigger match evaluation — called when timer expires or both players submit."""
    try:
        async with AsyncSessionLocal() as db:
            from app.services.challenge_evaluation_service import evaluate_match
            await evaluate_match(db, UUID(match_id))
            await db.commit()
    except Exception as e:
        logger.error(f"[WS] Evaluation trigger failed for {match_id}: {e}", exc_info=True)


async def _timer_loop(match_id: str, remaining_seconds: int) -> None:
    """
    Server-side countdown timer.
    Ticks every 5 seconds, broadcasts remaining time, triggers evaluation at 0.
    """
    tick = 5
    elapsed = 0

    while elapsed < remaining_seconds:
        await asyncio.sleep(tick)
        elapsed += tick
        left = max(0, remaining_seconds - elapsed)
        await broadcast_to_room(match_id, "timer_tick", {"remaining_seconds": left})
        if left == 0:
            break

    # Timer expired — trigger evaluation
    _timer_tasks.pop(match_id, None)
    await _trigger_evaluation(match_id)


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@ws_challenges_router.websocket("/ws/challenges/{match_id}")
async def challenge_room_ws(
    websocket: WebSocket,
    match_id: str,
    token: str = Query(...),
) -> None:
    # ── Auth — accept both Firebase JWT and challenge JWT ─────────────────────
    user_id: str | None = None
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # First try challenge JWT (used by the web room app)
        try:
            from app.services.challenge_link_service import verify_challenge_token
            payload = verify_challenge_token(token)
            token_match_id = payload.get("match_id")
            token_user_id = payload.get("user_id")
            if token_match_id == match_id and token_user_id:
                user_id = token_user_id
        except Exception:
            pass

        # Fall back to Firebase JWT (used by the Flutter app)
        if not user_id:
            try:
                user = await verify_token(token, db)
                user_id = str(user.id)
            except Exception:
                await websocket.close(code=4001)
                return

        try:
            match_uuid = UUID(match_id)
        except ValueError:
            await websocket.close(code=4004)
            return

        result = await db.execute(select(Match).where(Match.id == match_uuid))
        match = result.scalar_one_or_none()

    if not match:
        await websocket.close(code=4004)
        return

    # Spectators are anyone who is not challenger or opponent
    is_spectator = (
        str(match.challenger_id) != user_id
        and str(match.opponent_id) != user_id
    )

    await websocket.accept()

    conn = (websocket, user_id, is_spectator)
    _rooms[match_id].add(conn)

    logger.info(
        f"[WS] {'Spectator' if is_spectator else 'Player'} {user_id} "
        f"joined match {match_id} (status={match.status})"
    )

    # ── Compute remaining time ────────────────────────────────────────────────
    remaining = 0
    if match.started_at and match.status == "active":
        now = datetime.utcnow()
        duration_secs = match.duration_minutes * 60
        elapsed_secs = int((now - match.started_at).total_seconds())
        remaining = max(0, duration_secs - elapsed_secs)

    # ── Send initial state ────────────────────────────────────────────────────
    await _send(websocket, "connection_status", {"connected": True})
    await _send(websocket, "timer_start", {"remaining_seconds": remaining})

    # ── Start server-side timer if not already running ────────────────────────
    if (
        match.status == "active"
        and remaining > 0
        and match_id not in _timer_tasks
    ):
        task = asyncio.create_task(_timer_loop(match_id, remaining))
        _timer_tasks[match_id] = task

    await _broadcast_spectator_count(match_id)

    # ── Message loop ──────────────────────────────────────────────────────────
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "status_update" and not is_spectator:
                status = msg.get("status", "working")
                # Forward status to the other player only
                for ws, uid, spec in list(_rooms.get(match_id, set())):
                    if uid != user_id and not spec:
                        await _send(ws, "opponent_status", {"status": status})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[WS] Error for {user_id} in match {match_id}: {e}")
    finally:
        _rooms[match_id].discard(conn)
        if not _rooms[match_id]:
            _rooms.pop(match_id, None)
        await _broadcast_spectator_count(match_id)
        logger.info(f"[WS] {user_id} disconnected from match {match_id}")
