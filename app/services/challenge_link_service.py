"""
Challenge link generation service.

Generates a signed JWT URL that both players open in the external
challenge room web app (challenges.hirex.com / hirex-challenge-room.vercel.app).

Token payload:
  match_id  — UUID of the match
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


def generate_challenge_link(match_id: UUID) -> str:
    """
    Return the full external challenge room URL for a given match.

    Both the challenger and opponent receive the same link.
    The external web app identifies the user via their own Firebase token
    (passed separately in the web app's auth flow), so the link itself
    only needs to carry the match_id.
    """
    now = int(time.time())
    payload = {
        "match_id": str(match_id),
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    token = jwt.encode(payload, settings.challenge_jwt_secret, algorithm=_ALGORITHM)
    base = settings.challenge_room_base_url.rstrip("/")
    return f"{base}/room/{match_id}?token={token}"


def verify_challenge_token(token: str) -> dict:
    """
    Decode and verify a challenge room JWT.
    Raises jose.JWTError on invalid / expired tokens.
    """
    return jwt.decode(token, settings.challenge_jwt_secret, algorithms=[_ALGORITHM])
