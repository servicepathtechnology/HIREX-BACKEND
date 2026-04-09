"""FastAPI dependencies — auth middleware and DB session injection."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that extracts and validates the Firebase JWT from the
    Authorization header, then returns the corresponding User record.
    """
    token = credentials.credentials
    decoded = await verify_firebase_token(token)
    firebase_uid = decoded.get("uid")

    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

    # Fallback: look up by email in case firebase_uid changed
    if not user:
        email = decoded.get("email")
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                user.firebase_uid = firebase_uid
                await db.flush()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please register first.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled.",
        )

    if getattr(user, "is_suspended", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Contact support.",
        )

    return user


async def get_current_recruiter(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the current user has the recruiter role."""
    if current_user.role != "recruiter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Recruiter role required.",
        )
    return current_user


async def verify_token(token: str, db: AsyncSession) -> User:
    """Verify a raw JWT token string — used for WebSocket auth."""
    decoded = await verify_firebase_token(token)
    firebase_uid = decoded.get("uid")

    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    return user
