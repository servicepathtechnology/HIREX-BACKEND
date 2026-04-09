"""FCM push notification service — Part 4."""

import logging
from uuid import UUID

from firebase_admin import messaging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.part4 import FCMToken
from app.models.recruiter import Notification

logger = logging.getLogger(__name__)

# Default notification preferences
DEFAULT_PREFS = {
    "submission_scored": True,
    "shortlisted": True,
    "stage_changed": True,
    "hired": True,
    "new_message": True,
    "new_submission": True,
    "ai_scoring_complete": True,
    "submission_count_milestone": False,
    "task_closed": True,
}


async def get_active_fcm_tokens(db: AsyncSession, user_id: UUID) -> list[FCMToken]:
    result = await db.execute(
        select(FCMToken).where(
            FCMToken.user_id == user_id,
            FCMToken.is_active == True,
        )
    )
    return result.scalars().all()


async def deactivate_fcm_token(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(FCMToken).where(FCMToken.token == token))
    fcm = result.scalar_one_or_none()
    if fcm:
        fcm.is_active = False
        await db.flush()


async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    return result.scalar() or 0


async def send_push_notification(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    body: str,
    data: dict,
    notif_type: str,
) -> None:
    """Send FCM push to all active devices for a user, respecting notification prefs."""
    from app.models.user import User
    # Check notification preferences
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        prefs = user.notification_prefs or DEFAULT_PREFS
        if not prefs.get(notif_type, DEFAULT_PREFS.get(notif_type, True)):
            logger.debug(f"Push suppressed for {user_id}: {notif_type} disabled in prefs")
            return

    tokens = await get_active_fcm_tokens(db, user_id)
    if not tokens:
        return

    badge_count = await get_unread_count(db, user_id)

    try:
        message = messaging.MulticastMessage(
            tokens=[t.token for t in tokens],
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", badge=badge_count)
                )
            ),
        )
        response = messaging.send_each_for_multicast(message)

        # Handle stale tokens
        for i, result in enumerate(response.responses):
            if not result.success:
                err = str(result.exception) if result.exception else ""
                if "registration-token-not-registered" in err.lower() or "invalid-registration-token" in err.lower():
                    await deactivate_fcm_token(db, tokens[i].token)
                    logger.info(f"Deactivated stale FCM token for user {user_id}")

        logger.info(f"FCM push sent to {user_id}: {response.success_count}/{len(tokens)} delivered")

    except Exception as e:
        logger.error(f"FCM send failed for {user_id}: {e}")


# ── Typed notification helpers ────────────────────────────────────────────────

async def push_submission_scored(db, candidate_id, task_title, total_score, submission_id):
    await send_push_notification(
        db, candidate_id,
        title="Your Score is In!",
        body=f"You scored {total_score:.0f}/100 on {task_title}. See your results.",
        data={"type": "submission_scored", "submission_id": str(submission_id)},
        notif_type="submission_scored",
    )


async def push_shortlisted(db, candidate_id, company_name, task_title, task_id):
    await send_push_notification(
        db, candidate_id,
        title="You've Been Shortlisted!",
        body=f"{company_name} shortlisted you for {task_title}. Check your pipeline.",
        data={"type": "shortlisted", "task_id": str(task_id)},
        notif_type="shortlisted",
    )


async def push_stage_changed(db, candidate_id, task_title, stage, pipeline_id):
    await send_push_notification(
        db, candidate_id,
        title="Application Update",
        body=f"Your application for {task_title} moved to {stage.replace('_', ' ').title()}.",
        data={"type": "stage_changed", "pipeline_id": str(pipeline_id)},
        notif_type="stage_changed",
    )


async def push_hired(db, candidate_id, task_title, task_id):
    await send_push_notification(
        db, candidate_id,
        title="Congratulations!",
        body=f"You've been hired through HireX for {task_title}!",
        data={"type": "hired", "task_id": str(task_id)},
        notif_type="hired",
    )


async def push_ai_scoring_complete(db, recruiter_id, task_title, task_id, count):
    await send_push_notification(
        db, recruiter_id,
        title="AI Review Ready",
        body=f"AI scoring complete for {count} submissions on {task_title}.",
        data={"type": "ai_scoring_complete", "task_id": str(task_id)},
        notif_type="ai_scoring_complete",
    )


async def push_new_message(db, recipient_id, sender_name, preview, thread_id):
    await send_push_notification(
        db, recipient_id,
        title="New Message",
        body=f"{sender_name}: {preview[:60]}...",
        data={"type": "new_message", "thread_id": str(thread_id)},
        notif_type="new_message",
    )


async def push_new_submission(db, recruiter_id, task_title, task_id, count):
    await send_push_notification(
        db, recruiter_id,
        title="New Submission",
        body=f"{task_title} received a new submission. Total: {count}.",
        data={"type": "new_submission", "task_id": str(task_id)},
        notif_type="new_submission",
    )
