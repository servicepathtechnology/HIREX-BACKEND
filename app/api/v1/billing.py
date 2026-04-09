"""Billing API — Razorpay order creation, payment verification, task unlock."""

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.dependencies import get_current_recruiter
from app.core.config import settings
from app.models.user import User
from app.models.task import Task
from app.models.recruiter import TaskPayment, RecruiterAnalytics
from app.schemas.recruiter import (
    CreateOrderRequest, CreateOrderResponse,
    VerifyPaymentRequest, VerifyPaymentResponse,
    PaymentHistoryResponse, PaginatedPaymentHistoryResponse,
)
from app.services.razorpay_service import (
    create_razorpay_order, verify_razorpay_signature, get_tier_amount,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> CreateOrderResponse:
    # Verify task ownership
    task_result = await db.execute(select(Task).where(Task.id == payload.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.recruiter_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.is_published:
        raise HTTPException(status_code=400, detail="Task is already published.")

    tier = payload.tier.lower()
    amount_paise = get_tier_amount(tier)

    # Create Razorpay order
    order_data = await create_razorpay_order(
        amount_paise=amount_paise,
        currency="INR",
        receipt=f"hirex_{task.id}",
        notes={"task_id": str(task.id), "tier": tier},
    )

    # Store pending payment record
    payment = TaskPayment(
        recruiter_id=current_user.id,
        task_id=task.id,
        razorpay_order_id=order_data["id"],
        amount_paise=amount_paise,
        currency="INR",
        status="pending",
        tier=tier,
    )
    db.add(payment)

    # Update task tier
    task.tier = tier
    await db.flush()

    return CreateOrderResponse(
        order_id=order_data["id"],
        amount=amount_paise,
        currency="INR",
        key_id=settings.razorpay_key_id or "rzp_test_placeholder",
        task_id=task.id,
        tier=tier,
    )


@router.post("/verify-payment", response_model=VerifyPaymentResponse)
async def verify_payment(
    payload: VerifyPaymentRequest,
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> VerifyPaymentResponse:
    # Find payment record
    payment_result = await db.execute(
        select(TaskPayment).where(
            TaskPayment.razorpay_order_id == payload.order_id,
            TaskPayment.recruiter_id == current_user.id,
        )
    )
    payment = payment_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    # Verify signature server-side — NEVER trust client
    is_valid = verify_razorpay_signature(
        order_id=payload.order_id,
        payment_id=payload.payment_id,
        signature=payload.signature,
    )

    if not is_valid:
        payment.status = "failed"
        await db.flush()
        raise HTTPException(
            status_code=400,
            detail="Payment signature verification failed. Contact support.",
        )

    # Update payment record
    payment.razorpay_payment_id = payload.payment_id
    payment.razorpay_signature = payload.signature
    payment.status = "paid"
    payment.paid_at = datetime.utcnow()

    # Publish the task
    task_result = await db.execute(select(Task).where(Task.id == payment.task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    # Check subscription task limit if recruiter has an active subscription
    recruiter_profile = current_user.recruiter_profile
    if recruiter_profile and recruiter_profile.subscription_status == "active" and recruiter_profile.active_task_limit:
        active_count_result = await db.execute(
            select(func.count(Task.id)).where(
                Task.recruiter_id == current_user.id,
                Task.is_published == True,
                Task.is_active == True,
            )
        )
        active_count = active_count_result.scalar() or 0
        if active_count >= recruiter_profile.active_task_limit:
            raise HTTPException(
                status_code=403,
                detail=f"Active task limit reached ({recruiter_profile.active_task_limit} tasks). Upgrade your subscription plan.",
            )

    task.is_published = True
    task.is_active = True

    # Create analytics row
    existing_analytics = await db.execute(
        select(RecruiterAnalytics).where(RecruiterAnalytics.task_id == task.id)
    )
    if not existing_analytics.scalar_one_or_none():
        analytics = RecruiterAnalytics(task_id=task.id)
        db.add(analytics)

    await db.flush()

    return VerifyPaymentResponse(
        success=True,
        task_id=task.id,
        message="Payment verified. Task published successfully.",
    )


@router.get("/history", response_model=PaginatedPaymentHistoryResponse)
async def get_payment_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_recruiter),
    db: AsyncSession = Depends(get_db),
) -> PaginatedPaymentHistoryResponse:
    query = select(TaskPayment).where(
        TaskPayment.recruiter_id == current_user.id
    ).order_by(TaskPayment.created_at.desc())

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    payments = result.scalars().all()

    items = []
    for p in payments:
        task_result = await db.execute(select(Task).where(Task.id == p.task_id))
        task = task_result.scalar_one_or_none()
        items.append(PaymentHistoryResponse(
            id=p.id,
            task_id=p.task_id,
            task_title=task.title if task else None,
            tier=p.tier,
            amount_paise=p.amount_paise,
            currency=p.currency,
            status=p.status,
            razorpay_order_id=p.razorpay_order_id,
            razorpay_payment_id=p.razorpay_payment_id,
            paid_at=p.paid_at,
            created_at=p.created_at,
        ))

    return PaginatedPaymentHistoryResponse(
        items=items, total=total, page=page, page_size=page_size,
        has_more=(offset + len(items)) < total,
    )
