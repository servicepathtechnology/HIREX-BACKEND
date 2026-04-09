"""Badge award logic — called after submission scoring."""

from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Submission


BADGE_DEFINITIONS = [
    {
        "id": "first_submission",
        "name": "First Step",
        "description": "Completed your first submission",
        "earn_condition": "Complete first submission",
    },
    {
        "id": "top_10",
        "name": "Top 10%",
        "description": "Finished in top 10% on a task",
        "earn_condition": "Finish in top 10% on any task",
    },
    {
        "id": "top_3",
        "name": "Podium Finish",
        "description": "Finished in top 3 on a task",
        "earn_condition": "Finish in top 3 on any task",
    },
    {
        "id": "multi_domain",
        "name": "Versatile",
        "description": "Submitted in 3+ different domains",
        "earn_condition": "Submit in 3+ different domains",
    },
    {
        "id": "streak_5",
        "name": "On a Roll",
        "description": "Submitted 5 tasks in 7 days",
        "earn_condition": "Submit 5 tasks in 7 days",
    },
    {
        "id": "perfect_score",
        "name": "Perfect 100",
        "description": "Achieved 100/100 on a task",
        "earn_condition": "Achieve 100/100 on any task",
    },
    {
        "id": "speed_demon",
        "name": "Speed Demon",
        "description": "Scored in top 10% with lowest time spent",
        "earn_condition": "Score in top 10% with lowest time_spent",
    },
    {
        "id": "comeback",
        "name": "Comeback Kid",
        "description": "Scored 80+ after previously scoring below 50",
        "earn_condition": "Score 80+ after previously scoring below 50",
    },
]


async def compute_earned_badges(candidate_id, db: AsyncSession) -> List[dict]:
    """Compute which badges a candidate has earned based on their submissions."""
    result = await db.execute(
        select(Submission).where(
            Submission.candidate_id == candidate_id,
            Submission.status.in_(["submitted", "under_review", "scored"]),
        )
    )
    submissions = result.scalars().all()

    scored = [s for s in submissions if s.status == "scored" and s.total_score is not None]
    earned_ids = set()
    earned_at = {}

    # first_submission
    if submissions:
        earned_ids.add("first_submission")
        earned_at["first_submission"] = min(s.submitted_at or s.created_at for s in submissions)

    # top_10 — percentile >= 90
    for s in scored:
        if s.percentile is not None and s.percentile >= 90:
            earned_ids.add("top_10")
            earned_at.setdefault("top_10", s.submitted_at)

    # top_3 — rank <= 3
    for s in scored:
        if s.rank is not None and s.rank <= 3:
            earned_ids.add("top_3")
            earned_at.setdefault("top_3", s.submitted_at)

    # multi_domain — 3+ different domains
    from sqlalchemy import select as sel
    from app.models.task import Task
    task_ids = [s.task_id for s in submissions]
    if task_ids:
        tasks_result = await db.execute(sel(Task).where(Task.id.in_(task_ids)))
        tasks = tasks_result.scalars().all()
        domains = set(t.domain for t in tasks)
        if len(domains) >= 3:
            earned_ids.add("multi_domain")
            earned_at.setdefault("multi_domain", datetime.utcnow())

    # streak_5 — 5 submissions in 7 days
    submitted_dates = sorted(
        [s.submitted_at for s in submissions if s.submitted_at],
        reverse=True,
    )
    if len(submitted_dates) >= 5:
        for i in range(len(submitted_dates) - 4):
            window = submitted_dates[i:i + 5]
            if (window[0] - window[4]).days <= 7:
                earned_ids.add("streak_5")
                earned_at.setdefault("streak_5", window[4])
                break

    # perfect_score
    for s in scored:
        if s.total_score is not None and s.total_score >= 100:
            earned_ids.add("perfect_score")
            earned_at.setdefault("perfect_score", s.submitted_at)

    # speed_demon — top 10% percentile with time_spent recorded
    for s in scored:
        if (s.percentile is not None and s.percentile >= 90
                and s.time_spent_minutes is not None):
            earned_ids.add("speed_demon")
            earned_at.setdefault("speed_demon", s.submitted_at)

    # comeback — scored 80+ after previously scoring below 50
    if len(scored) >= 2:
        sorted_scored = sorted(scored, key=lambda s: s.submitted_at or s.created_at)
        had_low = False
        for s in sorted_scored:
            if had_low and s.total_score is not None and s.total_score >= 80:
                earned_ids.add("comeback")
                earned_at.setdefault("comeback", s.submitted_at)
                break
            if s.total_score is not None and s.total_score < 50:
                had_low = True

    badges = []
    for defn in BADGE_DEFINITIONS:
        badges.append({
            **defn,
            "earned": defn["id"] in earned_ids,
            "earned_at": earned_at.get(defn["id"]),
        })
    return badges
