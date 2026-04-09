"""WebSocket handler for real-time messaging — Part 4."""

import json
import logging
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory map: user_id -> list of WebSocket connections
_connections: dict[str, list[WebSocket]] = {}


def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def connect(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    if user_id not in _connections:
        _connections[user_id] = []
    _connections[user_id].append(websocket)
    logger.info(f"WS connected: user {user_id} ({len(_connections[user_id])} connections)")


def disconnect(websocket: WebSocket, user_id: str) -> None:
    if user_id in _connections:
        _connections[user_id] = [ws for ws in _connections[user_id] if ws != websocket]
        if not _connections[user_id]:
            del _connections[user_id]
    logger.info(f"WS disconnected: user {user_id}")


async def send_to_user(user_id: str, payload: dict) -> None:
    """Send a message to all WebSocket connections for a user."""
    connections = _connections.get(user_id, [])
    dead = []
    for ws in connections:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections[user_id] = [c for c in _connections.get(user_id, []) if c != ws]


async def publish_message(recipient_id: str, payload: dict) -> None:
    """Publish message to Redis Pub/Sub for cross-instance delivery."""
    try:
        r = _get_redis()
        await r.publish(f"ws:user:{recipient_id}", json.dumps(payload))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Redis publish failed: {e}")
        # Fall back to direct delivery
        await send_to_user(recipient_id, payload)


async def handle_websocket(websocket: WebSocket, user_id: str) -> None:
    """Main WebSocket connection handler."""
    await connect(websocket, user_id)

    # Subscribe to Redis channel for this user
    r = _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"ws:user:{user_id}")

    import asyncio

    async def _redis_listener():
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    await send_to_user(user_id, data)
                except Exception as e:
                    logger.warning(f"Redis listener error: {e}")

    listener_task = asyncio.create_task(_redis_listener())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        listener_task.cancel()
        await pubsub.unsubscribe(f"ws:user:{user_id}")
        await r.aclose()
        disconnect(websocket, user_id)
