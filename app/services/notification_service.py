"""Notification creation service — called internally after scoring, shortlisting, stage changes."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.recruiter import Notification
from app.models.task import Task


async def create_notification(
    db: AsyncSession,
    user_id: UUID,
    notif_type: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        body=body,
        data=data or {},
    )
    db.add(notif)
    await db.flush()
    return notif


async def notify_submission_scored(
    db: AsyncSession,
    candidate_id: UUID,
    task_id: UUID,
    task_title: str,
    total_score: float,
    submission_id: UUID,
) -> None:
    await create_notification(
        db=db,
        user_id=candidate_id,
        notif_type="submission_scored",
        title="Your submission has been scored!",
        body=f"Your submission for '{task_title}' has been scored! You scored {total_score:.1f}/100.",
        data={"task_id": str(task_id), "submission_id": str(submission_id)},
    )


async def notify_shortlisted(
    db: AsyncSession,
    candidate_id: UUID,
    task_id: UUID,
    task_title: str,
    company_name: str,
    submission_id: UUID,
) -> None:
    await create_notification(
        db=db,
        user_id=candidate_id,
        notif_type="shortlisted",
        title="You've been shortlisted!",
        body=f"Great news! You've been shortlisted for '{task_title}' at {company_name}.",
        data={"task_id": str(task_id), "submission_id": str(submission_id)},
    )


async def notify_stage_changed(
    db: AsyncSession,
    candidate_id: UUID,
    task_id: UUID,
    task_title: str,
    stage: str,
    pipeline_id: UUID,
) -> None:
    stage_display = stage.replace("_", " ").title()
    if stage == "hired":
        title = "Congratulations! You've been hired!"
        body = f"Congratulations! You have been hired through HireX for '{task_title}'!"
        notif_type = "hired"
    else:
        title = "Application status updated"
        body = f"Your application for '{task_title}' has moved to {stage_display}."
        notif_type = "stage_changed"

    await create_notification(
        db=db,
        user_id=candidate_id,
        notif_type=notif_type,
        title=title,
        body=body,
        data={"task_id": str(task_id), "stage": stage, "pipeline_id": str(pipeline_id)},
    )


async def notify_new_submission(
    db: AsyncSession,
    recruiter_id: UUID,
    task_id: UUID,
    task_title: str,
    submission_id: UUID,
) -> None:
    await create_notification(
        db=db,
        user_id=recruiter_id,
        notif_type="new_submission",
        title="New submission received",
        body=f"New submission received for '{task_title}' from a candidate.",
        data={"task_id": str(task_id), "submission_id": str(submission_id)},
    )


async def notify_submission_count_milestone(
    db: AsyncSession,
    recruiter_id: UUID,
    task_id: UUID,
    task_title: str,
    count: int,
) -> None:
    await create_notification(
        db=db,
        user_id=recruiter_id,
        notif_type="submission_count_milestone",
        title=f"Milestone: {count} submissions!",
        body=f"Your task '{task_title}' has received {count} submissions!",
        data={"task_id": str(task_id), "count": count},
    )
