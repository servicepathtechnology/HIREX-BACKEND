"""FCM token registration API — Part 4."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.part4 import FCMToken
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["fcm"])


class FCMTokenRequest(BaseModel):
    token: str
    platform: str  # android | ios


class NotificationPrefsRequest(BaseModel):
    prefs: dict


@router.post("/fcm-token", status_code=204)
async def register_fcm_token(
    payload: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Register or update FCM token for current user."""
    if payload.platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="Platform must be 'android' or 'ios'.")

    existing = await db.execute(select(FCMToken).where(FCMToken.token == payload.token))
    token_row = existing.scalar_one_or_none()

    if token_row:
        token_row.user_id = current_user.id
        token_row.is_active = True
        from datetime import datetime
        token_row.last_used_at = datetime.utcnow()
    else:
        token_row = FCMToken(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform,
        )
        db.add(token_row)

    await db.flush()


@router.delete("/fcm-token", status_code=204)
async def deregister_fcm_token(
    payload: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deregister FCM token on logout."""
    existing = await db.execute(
        select(FCMToken).where(
            FCMToken.token == payload.token,
            FCMToken.user_id == current_user.id,
        )
    )
    token_row = existing.scalar_one_or_none()
    if token_row:
        token_row.is_active = False
        await db.flush()


@router.put("/prefs", status_code=204)
async def update_notification_prefs(
    payload: NotificationPrefsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update notification preferences for current user."""
    from sqlalchemy import select as sel
    from app.models.user import CandidateProfile
    user_result = await db.execute(sel(User).where(User.id == current_user.id))
    user = user_result.scalar_one_or_none()
    if user:
        existing_prefs = user.notification_prefs or {}
        existing_prefs.update(payload.prefs)
        user.notification_prefs = existing_prefs
        await db.flush()


@router.get("/prefs")
async def get_notification_prefs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get notification preferences for current user."""
    from backend.notifications.fcm_service import DEFAULT_PREFS
    user_result = await db.execute(select(User).where(User.id == current_user.id))
    user = user_result.scalar_one_or_none()
    prefs = DEFAULT_PREFS.copy()
    if user and user.notification_prefs:
        prefs.update(user.notification_prefs)
    return {"prefs": prefs}
