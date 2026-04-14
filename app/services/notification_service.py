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


async def notify_stage_changed(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    task_id: uuid.UUID,
    task_title: str,
    stage: str,
    pipeline_id: uuid.UUID,
) -> None:
    """Create in-app notification when pipeline stage changes.
    
    Args:
        db: Database session
        candidate_id: Candidate user ID
        task_id: Task ID
        task_title: Task title
        stage: New pipeline stage
        pipeline_id: Pipeline entry ID
    """
    try:
        from app.models.recruiter import Notification
        
        # Create user-friendly stage messages
        stage_messages = {
            "shortlisted": "You've been shortlisted!",
            "interviewing": "You've been moved to interviewing stage!",
            "offer_sent": "🎉 An offer has been sent to you!",
            "hired": "🎊 Congratulations! You've been hired!",
            "rejected": "Your application status has been updated",
        }
        
        title = stage_messages.get(stage, "Pipeline status updated")
        body = f"Your status for '{task_title}' has been updated to: {stage}"
        
        notification = Notification(
            user_id=candidate_id,
            type="stage_changed",
            title=title,
            body=body,
            data={
                "task_id": str(task_id),
                "pipeline_id": str(pipeline_id),
                "stage": stage,
            },
        )
        db.add(notification)
        await db.flush()
        
        logger.info(
            f"✅ Created stage_changed notification for candidate {candidate_id} (stage: {stage})"
        )
    except Exception as e:
        logger.error(f"Failed to create stage_changed notification: {e}")


async def notify_new_submission(
    db: AsyncSession,
    recruiter_id: uuid.UUID,
    candidate_id: uuid.UUID,
    task_id: uuid.UUID,
    task_title: str,
    submission_id: uuid.UUID,
) -> None:
    """Create in-app notification when candidate submits to recruiter's task.
    
    Args:
        db: Database session
        recruiter_id: Recruiter user ID
        candidate_id: Candidate user ID
        task_id: Task ID
        task_title: Task title
        submission_id: Submission ID
    """
    try:
        from app.models.recruiter import Notification
        
        notification = Notification(
            user_id=recruiter_id,
            type="new_submission",
            title="New submission received!",
            body=f"A candidate submitted to your task '{task_title}'",
            data={
                "task_id": str(task_id),
                "submission_id": str(submission_id),
                "candidate_id": str(candidate_id),
            },
        )
        db.add(notification)
        await db.flush()
        
        logger.info(
            f"✅ Created new_submission notification for recruiter {recruiter_id}"
        )
    except Exception as e:
        logger.error(f"Failed to create new_submission notification: {e}")


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    notif_type: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Generic function to create in-app notification.
    
    Args:
        db: Database session
        user_id: Target user ID
        notif_type: Notification type
        title: Notification title
        body: Notification body
        data: Additional data payload
    """
    try:
        from app.models.recruiter import Notification
        
        notification = Notification(
            user_id=user_id,
            type=notif_type,
            title=title,
            body=body,
            data=data,
        )
        db.add(notification)
        await db.flush()
        
        logger.info(
            f"✅ Created {notif_type} notification for user {user_id}"
        )
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
