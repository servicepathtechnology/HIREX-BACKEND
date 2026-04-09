"""Smart task recommendation engine — Part 4."""

import json
import logging
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import CandidateProfile
from app.models.task import Task, Submission
from app.models.part4 import RecommendationSignal

logger = logging.getLogger(__name__)

CACHE_TTL = 6 * 3600  # 6 hours
SIGNAL_WEIGHTS = {
    "skill_tag_match": 0.35,
    "domain_affinity": 0.25,
    "difficulty_match": 0.20,
    "past_performance": 0.15,
    "engagement": 0.05,
}

DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced", "expert"]


def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_recommendations(
    db: AsyncSession,
    candidate_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    """Get recommended tasks for a candidate. Uses Redis cache."""
    cache_key = f"recommendations:{candidate_id}"

    # Try cache
    r = _get_redis()
    try:
        cached = await r.get(cache_key)
        if cached:
            all_tasks = json.loads(cached)
            offset = (page - 1) * page_size
            return all_tasks[offset: offset + page_size]
    except Exception as e:
        logger.warning(f"Redis cache miss: {e}")
    finally:
        await r.aclose()

    # Compute recommendations
    ranked = await _compute_recommendations(db, candidate_id)

    # Cache result
    r = _get_redis()
    try:
        await r.setex(cache_key, CACHE_TTL, json.dumps(ranked))
    except Exception:
        pass
    finally:
        await r.aclose()

    offset = (page - 1) * page_size
    return ranked[offset: offset + page_size]


async def invalidate_cache(candidate_id: UUID) -> None:
    r = _get_redis()
    try:
        await r.delete(f"recommendations:{candidate_id}")
    except Exception:
        pass
    finally:
        await r.aclose()


async def _compute_recommendations(db: AsyncSession, candidate_id: UUID) -> list[dict]:
    # Get candidate profile
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == candidate_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Get already-attempted task IDs
    attempted_result = await db.execute(
        select(Submission.task_id).where(Submission.candidate_id == candidate_id)
    )
    attempted_ids = {row[0] for row in attempted_result.all()}

    # Get all active published tasks not yet attempted
    tasks_result = await db.execute(
        select(Task).where(
            Task.is_active == True,
            Task.is_published == True,
            Task.id.not_in(attempted_ids) if attempted_ids else True,
        )
    )
    tasks = tasks_result.scalars().all()

    if not tasks:
        return []

    # Cold start: no profile or no history
    if not profile or not profile.skill_tags:
        # Return top 20 by submission count
        sorted_tasks = sorted(tasks, key=lambda t: t.submission_count or 0, reverse=True)
        return [_task_to_dict(t, 0.0, []) for t in sorted_tasks[:20]]

    # Get engagement signals
    signals_result = await db.execute(
        select(RecommendationSignal).where(
            RecommendationSignal.candidate_id == candidate_id
        )
    )
    signals = signals_result.scalars().all()
    signal_map: dict[str, float] = {}
    for s in signals:
        tid = str(s.task_id)
        signal_map[tid] = signal_map.get(tid, 0) + s.signal_weight

    # Get scored submissions for performance signals
    scored_result = await db.execute(
        select(Submission).where(
            Submission.candidate_id == candidate_id,
            Submission.status == "scored",
            Submission.total_score >= 70,
        )
    )
    high_scored = scored_result.scalars().all()
    high_perf_task_ids = {str(s.task_id) for s in high_scored}

    # Determine candidate's average difficulty
    all_scored_result = await db.execute(
        select(Submission).where(
            Submission.candidate_id == candidate_id,
            Submission.status == "scored",
        )
    )
    all_scored = all_scored_result.scalars().all()

    # Get task difficulties for scored submissions
    scored_task_ids = [s.task_id for s in all_scored]
    avg_difficulty_idx = 1  # default: intermediate
    if scored_task_ids:
        diff_result = await db.execute(
            select(Task.difficulty).where(Task.id.in_(scored_task_ids))
        )
        diffs = [row[0] for row in diff_result.all()]
        if diffs:
            avg_idx = sum(DIFFICULTY_ORDER.index(d) for d in diffs if d in DIFFICULTY_ORDER) / len(diffs)
            avg_difficulty_idx = min(int(avg_idx) + 1, len(DIFFICULTY_ORDER) - 1)

    target_difficulty = DIFFICULTY_ORDER[avg_difficulty_idx]

    # Domain scores
    domain_scores: dict = profile.scores or {}
    best_domain = max(domain_scores, key=lambda d: domain_scores[d]) if domain_scores else None

    skill_tags = [s.lower() for s in (profile.skill_tags or [])]

    # Score each task
    scored_tasks = []
    for task in tasks:
        score = _compute_relevance(
            task=task,
            skill_tags=skill_tags,
            best_domain=best_domain,
            target_difficulty=target_difficulty,
            high_perf_task_ids=high_perf_task_ids,
            signal_map=signal_map,
        )
        match_reasons = _get_match_reasons(task, skill_tags, best_domain)
        scored_tasks.append((task, score, match_reasons))

    scored_tasks.sort(key=lambda x: x[1], reverse=True)
    return [_task_to_dict(t, s, r) for t, s, r in scored_tasks]


def _compute_relevance(
    task: Task,
    skill_tags: list[str],
    best_domain: str | None,
    target_difficulty: str,
    high_perf_task_ids: set[str],
    signal_map: dict[str, float],
) -> float:
    score = 0.0

    # Skill tag match
    task_skills = [s.lower() for s in (task.skills_tested or [])]
    if skill_tags and task_skills:
        overlap = len(set(skill_tags) & set(task_skills))
        tag_score = min(overlap / max(len(task_skills), 1), 1.0)
        score += tag_score * SIGNAL_WEIGHTS["skill_tag_match"]

    # Domain affinity
    if best_domain and task.domain and task.domain.lower() == best_domain.lower():
        score += SIGNAL_WEIGHTS["domain_affinity"]

    # Difficulty match
    if task.difficulty == target_difficulty:
        score += SIGNAL_WEIGHTS["difficulty_match"]
    elif abs(DIFFICULTY_ORDER.index(task.difficulty) - DIFFICULTY_ORDER.index(target_difficulty)) == 1:
        score += SIGNAL_WEIGHTS["difficulty_match"] * 0.5

    # Past performance
    if str(task.id) in high_perf_task_ids:
        score += SIGNAL_WEIGHTS["past_performance"]

    # Engagement signals
    engagement = signal_map.get(str(task.id), 0)
    score += min(engagement, 1.0) * SIGNAL_WEIGHTS["engagement"]

    return round(score, 4)


def _get_match_reasons(task: Task, skill_tags: list[str], best_domain: str | None) -> list[str]:
    reasons = []
    task_skills = [s.lower() for s in (task.skills_tested or [])]
    matched = list(set(skill_tags) & set(task_skills))
    if matched:
        reasons.append(f"Matches your {', '.join(matched[:3])} skills")
    if best_domain and task.domain and task.domain.lower() == best_domain.lower():
        reasons.append(f"Strong {task.domain} score")
    return reasons


def _task_to_dict(task: Task, relevance_score: float, match_reasons: list[str]) -> dict:
    return {
        "id": str(task.id),
        "title": task.title,
        "slug": task.slug,
        "domain": task.domain,
        "difficulty": task.difficulty,
        "task_type": task.task_type,
        "skills_tested": task.skills_tested or [],
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "estimated_hours": task.estimated_hours,
        "submission_count": task.submission_count or 0,
        "tier": task.tier,
        "relevance_score": relevance_score,
        "match_reasons": match_reasons,
    }
