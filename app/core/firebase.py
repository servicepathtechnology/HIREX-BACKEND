"""Firebase Admin SDK initialization and JWT verification."""

import asyncio
import json
from functools import partial

import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status

from app.core.config import settings

_firebase_app = None


def init_firebase() -> None:
    """Initialize Firebase Admin SDK. Called once on app startup."""
    global _firebase_app
    if not firebase_admin._apps:
        # Priority: FIREBASE_CREDENTIALS_JSON env var (for cloud) > file path (for local)
        if settings.firebase_credentials_json:
            cred_dict = json.loads(settings.firebase_credentials_json)
            cred = credentials.Certificate(cred_dict)
        else:
            cred = credentials.Certificate(settings.firebase_credentials_path)
        _firebase_app = firebase_admin.initialize_app(cred)


def _verify_sync(id_token: str) -> dict:
    """Synchronous Firebase token verification (runs in thread pool)."""
    try:
        return auth.verify_id_token(id_token)
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


async def verify_firebase_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token asynchronously (offloaded to thread pool
    so it never blocks the async event loop).
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_verify_sync, id_token))
