"""Razorpay subscription service — create, cancel, webhook handling."""

import hashlib
import hmac
import httpx
import base64
import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User, RecruiterProfile

logger = logging.getLogger(__name__)

PLAN_LIMITS = {
    "starter": 3,
    "growth": 10,
    "enterprise": 9999,
}

PLAN_IDS_MONTHLY = {
    "starter": "plan_starter_monthly",
    "growth": "plan_growth_monthly",
    "enterprise": "plan_enterprise_monthly",
}

PLAN_IDS_ANNUAL = {
    "starter": "plan_starter_annual",
    "growth": "plan_growth_annual",
    "enterprise": "plan_enterprise_annual",
}


def _razorpay_auth() -> str:
    key_id = settings.razorpay_key_id or ""
    key_secret = settings.razorpay_key_secret or ""
    return base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()


async def create_razorpay_subscription(
    plan: str,
    billing_period: str,  # "monthly" | "annual"
    customer_email: str,
) -> Dict[str, Any]:
    """Call Razorpay POST /v1/subscriptions and return subscription object."""
    if not settings.razorpay_key_id:
        # Dev mock
        import uuid as _uuid
        return {
            "id": f"sub_mock_{_uuid.uuid4().hex[:16]}",
            "status": "created",
            "short_url": "https://rzp.io/mock",
        }

    plan_map = PLAN_IDS_ANNUAL if billing_period == "annual" else PLAN_IDS_MONTHLY
    plan_id = plan_map.get(plan, plan_map["starter"])
    total_count = 12 if billing_period == "annual" else 1

    payload = {
        "plan_id": plan_id,
        "total_count": total_count,
        "customer_notify": 1,
        "notes": {"email": customer_email, "plan": plan, "period": billing_period},
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.razorpay.com/v1/subscriptions",
            json=payload,
            headers={"Authorization": f"Basic {_razorpay_auth()}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()


async def cancel_razorpay_subscription(subscription_id: str) -> None:
    """Cancel a Razorpay subscription at period end."""
    if not settings.razorpay_key_id or subscription_id.startswith("sub_mock"):
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.razorpay.com/v1/subscriptions/{subscription_id}/cancel",
            json={"cancel_at_cycle_end": 1},
            headers={"Authorization": f"Basic {_razorpay_auth()}"},
            timeout=10.0,
        )


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook X-Razorpay-Signature header."""
    secret = settings.razorpay_key_secret or ""
    if not secret:
        return True  # dev mode
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_subscription_webhook(
    db: AsyncSession,
    event: str,
    payload: Dict[str, Any],
) -> None:
    """Process Razorpay subscription webhook events."""
    sub_data = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    subscription_id = sub_data.get("id", "")

    if not subscription_id:
        return

    result = await db.execute(
        select(RecruiterProfile).where(RecruiterProfile.subscription_id == subscription_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        logger.warning(f"No recruiter found for subscription {subscription_id}")
        return

    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalar_one_or_none()

    if event == "subscription.activated":
        profile.subscription_status = "active"
        profile.subscription_valid_until = _next_billing_date(sub_data)
        _send_notification(user, "Subscription activated", "Your HireX subscription is now active.")

    elif event == "subscription.charged":
        profile.subscription_status = "active"
        profile.subscription_valid_until = _next_billing_date(sub_data)
        _send_notification(user, "Payment successful", "Your subscription payment was successful.")

    elif event == "subscription.payment_failed":
        profile.subscription_status = "payment_failed"
        _send_notification(user, "Payment failed", "Update your payment method to keep your subscription active.")

    elif event == "subscription.cancelled":
        profile.subscription_status = "cancelled"

    elif event == "subscription.completed":
        profile.subscription_status = "expired"
        profile.active_task_limit = None
        _send_notification(user, "Subscription expired", "Renew your subscription to continue posting tasks.")

    elif event == "subscription.halted":
        profile.subscription_status = "cancelled"
        profile.active_task_limit = None

    await db.flush()


def _next_billing_date(sub_data: Dict) -> datetime:
    ts = sub_data.get("current_end") or sub_data.get("charge_at")
    if ts:
        return datetime.utcfromtimestamp(int(ts))
    return datetime.utcnow() + timedelta(days=30)


def _send_notification(user: "User | None", title: str, body: str) -> None:
    """Fire-and-forget notification — actual sending done via FCM service."""
    if user:
        logger.info(f"[NOTIF] {user.email}: {title} — {body}")
