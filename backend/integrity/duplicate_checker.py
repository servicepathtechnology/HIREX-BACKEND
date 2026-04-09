"""Duplicate submission detection via SHA-256 content hash."""

import hashlib
import re
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Submission
from app.models.part4 import AIScoringJob

logger = logging.getLogger(__name__)


def _normalize_content(text: str) -> str:
    """Normalize text for hashing: lowercase, strip whitespace."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_code(code: str) -> str:
    """Normalize code: remove comments, lowercase, strip whitespace."""
    # Remove single-line comments (// and #)
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"#.*?$", "", code, flags=re.MULTILINE)
    # Remove multi-line comments (/* */ and """ """)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    code = code.lower()
    code = re.sub(r"\s+", " ", code).strip()
    return code


def compute_content_hash(submission: Submission) -> str | None:
    """Compute SHA-256 hash of normalized submission content."""
    if submission.code_content:
        normalized = _normalize_code(submission.code_content)
    elif submission.text_content:
        normalized = _normalize_content(submission.text_content)
    else:
        return None

    if not normalized:
        return None

    return hashlib.sha256(normalized.encode()).hexdigest()


async def check_duplicate_and_flag(
    db: AsyncSession,
    submission: Submission,
) -> bool:
    """
    Check if submission content is a duplicate of another submission for the same task.
    If duplicate found, creates an AI scoring job with plagiarism flag.
    Returns True if duplicate detected.
    """
    content_hash = compute_content_hash(submission)
    if not content_hash:
        return False

    # Store hash on submission
    submission.content_hash = content_hash

    # Check for duplicates in same task
    result = await db.execute(
        select(Submission).where(
            Submission.task_id == submission.task_id,
            Submission.content_hash == content_hash,
            Submission.id != submission.id,
            Submission.status != "draft",
        )
    )
    duplicate = result.scalar_one_or_none()

    if duplicate:
        logger.warning(
            f"Duplicate submission detected: {submission.id} matches {duplicate.id} for task {submission.task_id}"
        )
        # Create a flagged AI scoring job
        job = AIScoringJob(
            submission_id=submission.id,
            task_id=submission.task_id,
            status="completed",
            ai_flags={
                "plagiarism_suspected": True,
                "ai_generated_suspected": False,
                "reason": f"Exact duplicate of submission {duplicate.id}",
            },
            recruiter_approved=None,
        )
        db.add(job)
        await db.flush()
        return True

    return False
