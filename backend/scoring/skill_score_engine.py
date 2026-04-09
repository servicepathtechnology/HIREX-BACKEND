"""Full AI-powered Skill Score Engine — Part 4."""

import hashlib
import json
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import CandidateProfile
from app.models.task import Submission
from app.models.part4 import SkillScoreSnapshot

logger = logging.getLogger(__name__)

DIFFICULTY_MULTIPLIER = {
    "beginner": 0.8,
    "intermediate": 1.0,
    "advanced": 1.3,
    "expert": 1.6,
}


def _base_delta(task_score: float) -> int:
    if task_score >= 90:
        return 50
    elif task_score >= 80:
        return 35
    elif task_score >= 70:
        return 20
    elif task_score >= 60:
        return 10
    elif task_score >= 50:
        return 5
    elif task_score >= 40:
        return -5
    else:
        return -15


def _rank_multiplier(rank: int, total: int) -> float:
    if total == 0:
        return 1.0
    percentile = (total - rank) / total * 100
    if percentile >= 90:
        return 1.5
    elif percentile >= 75:
        return 1.2
    elif percentile >= 50:
        return 1.0
    elif percentile >= 25:
        return 0.8
    else:
        return 0.6


def compute_delta(
    task_score: float,
    rank: int,
    total_submissions: int,
    difficulty: str,
) -> int:
    base = _base_delta(task_score)
    rm = _rank_multiplier(rank, total_submissions)
    dm = DIFFICULTY_MULTIPLIER.get(difficulty, 1.0)
    return round(base * rm * dm)


def _clamp(value: int, lo: int = 0, hi: int = 1000) -> int:
    return max(lo, min(hi, value))


def _compute_hash(
    candidate_id: str,
    overall_score: int,
    domain_scores: dict,
    created_at: str,
) -> str:
    payload = json.dumps(
        {
            "candidate_id": candidate_id,
            "overall_score": overall_score,
            "domain_scores": domain_scores,
            "created_at": created_at,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def _get_platform_percentile(
    db: AsyncSession, domain: str, score: int
) -> float:
    """Compute percentile of this score among all candidates in the domain."""
    result = await db.execute(
        select(func.count(CandidateProfile.id)).where(
            CandidateProfile.scores.op("->>")(domain).cast(
                __import__("sqlalchemy").Integer
            ) < score
        )
    )
    below = result.scalar() or 0
    total_result = await db.execute(select(func.count(CandidateProfile.id)))
    total = total_result.scalar() or 1
    return round((below / total) * 100, 1)


async def update_skill_score_v2(
    db: AsyncSession,
    candidate_id: UUID,
    domain: str,
    task_score: float,
    rank: int,
    total_submissions: int,
    difficulty: str,
    submission_id: UUID | None = None,
    task_title: str = "",
) -> None:
    """Full Part 4 skill score update with snapshot and hash."""
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == candidate_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        return

    delta = compute_delta(task_score, rank, total_submissions, difficulty)
    domain_scores: dict = dict(profile.scores or {})
    current_domain_score = domain_scores.get(domain, 0)
    new_domain_score = _clamp(current_domain_score + delta)
    domain_scores[domain] = new_domain_score

    # Weighted average for overall
    if domain_scores:
        new_overall = round(sum(domain_scores.values()) / len(domain_scores))
    else:
        new_overall = 0
    new_overall = _clamp(new_overall)

    # Percentile
    percentile_overall = round((new_overall / 1000) * 100, 1)
    percentile_by_domain = {d: round((s / 1000) * 100, 1) for d, s in domain_scores.items()}

    # Snapshot reason
    reason = f"Scored {task_score:.1f}/100 on {task_title or 'task'}, rank #{rank} of {total_submissions}"

    # Tamper-evident hash
    now_str = datetime.utcnow().isoformat()
    snap_hash = _compute_hash(str(candidate_id), new_overall, domain_scores, now_str)

    snapshot = SkillScoreSnapshot(
        candidate_id=candidate_id,
        overall_score=new_overall,
        domain_scores=domain_scores,
        percentile_overall=percentile_overall,
        percentile_by_domain=percentile_by_domain,
        snapshot_reason=reason,
        submission_id=submission_id,
        hash=snap_hash,
    )
    db.add(snapshot)

    # Update profile
    profile.skill_score = new_overall
    profile.scores = domain_scores

    await db.flush()
    logger.info(
        f"Skill score updated for {candidate_id}: {domain} {current_domain_score} → {new_domain_score} (delta {delta:+d})"
    )
