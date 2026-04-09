"""Rank recalculation engine — run inside a DB transaction after each scoring event."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Submission
from app.models.recruiter import RecruiterAnalytics


async def recalculate_ranks(db: AsyncSession, task_id: UUID) -> None:
    """
    Recalculate rank and percentile for ALL scored submissions for a task.
    Also updates recruiter_analytics row.
    Must be called inside an active transaction.
    """
    result = await db.execute(
        select(Submission).where(
            Submission.task_id == task_id,
            Submission.status == "scored",
            Submission.total_score.isnot(None),
        ).order_by(Submission.total_score.desc())
    )
    scored = result.scalars().all()
    total = len(scored)

    if total == 0:
        return

    for i, sub in enumerate(scored):
        rank = i + 1
        percentile = round(((total - rank) / total) * 100, 1)
        sub.rank = rank
        sub.percentile = percentile

    await db.flush()

    # Update analytics
    analytics_result = await db.execute(
        select(RecruiterAnalytics).where(RecruiterAnalytics.task_id == task_id)
    )
    analytics = analytics_result.scalar_one_or_none()

    scores = [s.total_score for s in scored if s.total_score is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    # Score distribution buckets
    distribution = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20:
            distribution["0-20"] += 1
        elif s <= 40:
            distribution["21-40"] += 1
        elif s <= 60:
            distribution["41-60"] += 1
        elif s <= 80:
            distribution["61-80"] += 1
        else:
            distribution["81-100"] += 1

    # Time stats
    time_values = [
        s.time_spent_minutes for s in scored
        if s.time_spent_minutes is not None
    ]
    avg_time = round(sum(time_values) / len(time_values), 1) if time_values else None

    if analytics is None:
        analytics = RecruiterAnalytics(
            task_id=task_id,
            scored_count=total,
            avg_score=avg_score,
            score_distribution=distribution,
            avg_time_spent_mins=avg_time,
        )
        db.add(analytics)
    else:
        analytics.scored_count = total
        analytics.avg_score = avg_score
        analytics.score_distribution = distribution
        analytics.avg_time_spent_mins = avg_time

    await db.flush()


async def update_candidate_skill_score(
    db: AsyncSession,
    candidate_id: UUID,
    domain: str,
    total_score: float,
    rank: int,
    total_scored: int,
) -> None:
    """Simple delta-based skill score update (Part 4 makes this AI-powered)."""
    from app.models.user import CandidateProfile
    from app.models.task import SkillScoreHistory

    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == candidate_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return

    # Delta: score above 50 gives positive delta, below gives negative
    base_delta = int((total_score - 50) / 5)
    # Rank bonus: top 10% gets +5
    rank_bonus = 5 if (rank / max(total_scored, 1)) <= 0.1 else 0
    delta = max(-10, min(20, base_delta + rank_bonus))

    current = profile.skill_score or 0
    new_score = max(0, min(1000, current + delta))
    profile.skill_score = new_score

    # Update domain scores in JSONB
    scores_dict = profile.scores or {}
    domain_score = scores_dict.get(domain, 0)
    scores_dict[domain] = max(0, min(1000, domain_score + delta))
    profile.scores = scores_dict

    # History entry
    history = SkillScoreHistory(
        candidate_id=candidate_id,
        domain=domain,
        score=new_score,
        delta=delta,
        reason=f"Scored {total_score:.1f}/100 on task (rank #{rank} of {total_scored})",
    )
    db.add(history)
    await db.flush()
