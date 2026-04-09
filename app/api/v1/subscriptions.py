"""Recruiter subscription endpoints — Razorpay subscription plans."""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.subscription_service import (
    PLAN_LIMITS,
    cancel_razorpay_subscription,
    create_razorpay_subscription,
    handle_subscription_webhook,
    verify_webhook_signature,
)
from app.core.database import get_db
from app.core.dependencies import get_current_recruiter
from app.models.user import User, RecruiterProfile
from app.models.task import Task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing/subscriptions", tags=["subscriptions"])
webhook_router = APIRouter(prefix="/billing", tags=["subscriptions"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateSubscriptionRequest(BaseModel):
    plan: str           # starter | growth | enterprise
    billing_period: str = "monthly"  # monthly | annual


class SubscriptionResponse(BaseModel):
    subscription_id: str
    short_url: Optional[str] = None
    plan: str
    billing_period: str
    status: str


class SubscriptionStatusResponse(BaseModel):
    plan: Optional[str]
    status: Optional[str]
    valid_until: Optional[datetime]
    active_task_limit: Optional[int]
    active_tasks_used: int
    subscription_id: Optional[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create", response_model=SubscriptionResponse)
async def create_subscription(
    payload: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    plan = payload.plan.lower()
    if plan not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    sub_data = await create_razorpay_subscription(
        plan=plan,
        billing_period=payload.billing_period,
        customer_email=current_user.email,
    )

    # Store subscription ID on recruiter profile
    profile = current_user.recruiter_profile
    if not profile:
        raise HTTPException(status_code=400, detail="Recruiter profile not found.")

    profile.subscription_id = sub_data["id"]
    profile.subscription_plan = plan
    profile.subscription_status = "created"
    profile.active_task_limit = PLAN_LIMITS[plan]
    await db.flush()

    return SubscriptionResponse(
        subscription_id=sub_data["id"],
        short_url=sub_data.get("short_url"),
        plan=plan,
        billing_period=payload.billing_period,
        status=sub_data.get("status", "created"),
    )


@router.get("/me", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionStatusResponse:
    profile = current_user.recruiter_profile
    if not profile:
        raise HTTPException(status_code=404, detail="Recruiter profile not found.")

    # Count active tasks
    active_count_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.recruiter_id == current_user.id,
            Task.is_published == True,
            Task.is_active == True,
        )
    )
    active_tasks_used = active_count_result.scalar() or 0

    return SubscriptionStatusResponse(
        plan=profile.subscription_plan,
        status=profile.subscription_status,
        valid_until=profile.subscription_valid_until,
        active_task_limit=profile.active_task_limit,
        active_tasks_used=active_tasks_used,
        subscription_id=profile.subscription_id,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_subscription(
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> None:
    profile = current_user.recruiter_profile
    if not profile or not profile.subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription.")

    await cancel_razorpay_subscription(profile.subscription_id)
    profile.subscription_status = "cancelled"
    await db.flush()


@webhook_router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle all Razorpay webhook events. Verifies signature before processing."""
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    import json
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = data.get("event", "")
    logger.info(f"[WEBHOOK] Razorpay event: {event}")

    subscription_events = {
        "subscription.activated", "subscription.charged",
        "subscription.payment_failed", "subscription.cancelled",
        "subscription.completed", "subscription.halted",
    }

    if event in subscription_events:
        await handle_subscription_webhook(db, event, data)

    return {"status": "ok"}
