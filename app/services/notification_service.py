"""Notification Service for FCM push notifications."""

import uuid
from typing import Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending push notifications via FCM."""

    async def send_push_notification(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send FCM push notification to user.
        
        Args:
            user_id: Target user ID
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            True if sent successfully
        """
        try:
            # TODO: Implement actual FCM sending
            # For now, just log
            logger.info(
                f"📱 Push notification to {user_id}: {title} - {body}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return False


async def notify_submission_scored(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    task_id: uuid.UUID,
    task_title: str,
    total_score: float,
    submission_id: uuid.UUID,
) -> None:
    """Create in-app notification when submission is scored.
    
    Args:
        db: Database session
        candidate_id: Candidate user ID
        task_id: Task ID
        task_title: Task title
        total_score: Score received
        submission_id: Submission ID
    """
    try:
        from app.models.recruiter import Notification
        
        notification = Notification(
            user_id=candidate_id,
            type="submission_scored",
            title="Your submission has been scored!",
            body=f"You scored {total_score:.1f}/100 on '{task_title}'",
            data={
                "task_id": str(task_id),
                "submission_id": str(submission_id),
                "score": total_score,
            },
        )
        db.add(notification)
        await db.flush()
        
        logger.info(
            f"✅ Created submission_scored notification for candidate {candidate_id}"
        )
    except Exception as e:
        logger.error(f"Failed to create submission_scored notification: {e}")


async def notify_shortlisted(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    task_id: uuid.UUID,
    task_title: str,
    company_name: str,
    submission_id: uuid.UUID,
) -> None:
    """Create in-app notification when candidate is shortlisted.
    
    Args:
        db: Database session
        candidate_id: Candidate user ID
        task_id: Task ID
        task_title: Task title
        company_name: Company name
        submission_id: Submission ID
    """
    try:
        from app.models.recruiter import Notification
        
        notification = Notification(
            user_id=candidate_id,
            type="shortlisted",
            title="🎉 You've been shortlisted!",
            body=f"{company_name} shortlisted you for '{task_title}'",
            data={
                "task_id": str(task_id),
                "submission_id": str(submission_id),
                "company_name": company_name,
            },
        )
        db.add(notification)
        await db.flush()
        
        logger.info(
            f"✅ Created shortlisted notification for candidate {candidate_id}"
        )
    except Exception as e:
        logger.error(f"Failed to create shortlisted notification: {e}")
