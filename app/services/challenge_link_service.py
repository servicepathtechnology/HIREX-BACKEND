"""
Challenge link generation service.

Generates a signed JWT URL that both players open in the external
challenge room web app (challenges.hirex.com / hirex-challenge-room.vercel.app).

Token payload:
  match_id  — UUID of the match
  user_id   — UUID of the user this link is for
  iat       — issued at (unix timestamp)
  exp       — expires at (iat + 4 hours, covers max 60-min match + buffer)
"""

from __future__ import annotations

import time
from uuid import UUID

from jose import jwt

from app.core.config import settings

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 4 * 3600  # 4 hours


def generate_challenge_link(match_id: UUID, user_id: UUID | None = None) -> str:
    """
    Return the full external challenge room URL for a given match and user.
    Each user gets their own token with their user_id embedded.
    """
    now = int(time.time())
    payload: dict = {
        "match_id": str(match_id),
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    if user_id is not None:
        payload["user_id"] = str(user_id)
    token = jwt.encode(payload, settings.challenge_jwt_secret, algorithm=_ALGORITHM)
    base = settings.challenge_room_base_url.rstrip("/")
    return f"{base}/room/{match_id}?token={token}"


def generate_challenge_link_for_user(match_id: UUID, user_id: UUID) -> str:
    """Generate a user-specific challenge room link."""
    return generate_challenge_link(match_id, user_id)


def verify_challenge_token(token: str) -> dict:
    """
    Decode and verify a challenge room JWT.
    Raises jose.JWTError on invalid / expired tokens.
    """
    return jwt.decode(token, settings.challenge_jwt_secret, algorithms=[_ALGORITHM])
