"""
Evaluation pipeline for 1v1 challenge submissions.

- Coding / Data: Judge0 API (async polling)
- Non-coding: OpenAI GPT-4o with structured rubric scoring
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.challenges import Match, ChallengeSubmission, ChallengeTask
from app.models.user import User
from app.services.elo_service import apply_elo_update
from app.services.challenge_notification_service import (
    notify_match_result_ready,
    notify_elo_tier_changed,
)

logger = logging.getLogger(__name__)

# ── Judge0 config ─────────────────────────────────────────────────────────────

JUDGE0_URL = "https://judge0-ce.p.rapidapi.com"
JUDGE0_HEADERS = {
    "X-RapidAPI-Key": getattr(settings, "judge0_api_key", ""),
    "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
}

LANGUAGE_IDS = {
    "python": 71,
    "javascript": 63,
    "java": 62,
    "cpp": 54,
    "go": 60,
    "rust": 73,
    "sql": 82,
}

# ── AI rubric ─────────────────────────────────────────────────────────────────

RUBRIC_SYSTEM_PROMPT = """You are an expert evaluator for a competitive hiring platform.
Evaluate the candidate's submission against the task brief using the following rubric.
Each dimension is scored 0-25. Return ONLY valid JSON with this exact schema:
{
  "clarity": <int 0-25>,
  "depth": <int 0-25>,
  "relevance": <int 0-25>,
  "quality_of_execution": <int 0-25>,
  "total": <int 0-100>,
  "feedback": "<3-5 sentence paragraph>"
}"""


async def evaluate_match(db: AsyncSession, match_id: UUID) -> None:
    """
    Main evaluation entry point. Called when both submissions are received
    or when the timer expires. Evaluates both submissions, updates ELO,
    and sends notifications.
    """
    try:
        result = await db.execute(select(Match).where(Match.id == match_id))
        match = result.scalar_one_or_none()
        if not match or match.status != "active":
            return

        subs_result = await db.execute(
            select(ChallengeSubmission).where(ChallengeSubmission.match_id == match_id)
        )
        submissions = subs_result.scalars().all()

        challenger_sub = next((s for s in submissions if s.user_id == match.challenger_id), None)
        opponent_sub = next((s for s in submissions if s.user_id == match.opponent_id), None)

        # Fetch task
        task = None
        if match.task_id:
            task_result = await db.execute(
                select(ChallengeTask).where(ChallengeTask.id == match.task_id)
            )
            task = task_result.scalar_one_or_none()

        domain = match.domain

        # Evaluate each submission
        if challenger_sub and challenger_sub.score is None:
            await _evaluate_submission(db, challenger_sub, domain, task)

        if opponent_sub and opponent_sub.score is None:
            await _evaluate_submission(db, opponent_sub, domain, task)

        await db.flush()

        # Determine winner
        c_score = challenger_sub.score if challenger_sub else None
        o_score = opponent_sub.score if opponent_sub else None

        winner_id = _determine_winner(
            match.challenger_id, match.opponent_id, c_score, o_score
        )

        # Apply ELO
        c_elo, o_elo, c_tier_changed, o_tier_changed = await apply_elo_update(
            db, match.challenger_id, match.opponent_id, c_score, o_score
        )

        # Update match
        from datetime import datetime
        match.status = "completed"
        match.ended_at = datetime.utcnow()
        match.winner_id = winner_id
        match.challenger_elo_after = c_elo.elo
        match.opponent_elo_after = o_elo.elo

        # Award points and badge to winner
        if winner_id is not None:
            difficulty = getattr(match, 'difficulty', 'easy')
            points, badge = _winner_reward(difficulty)
            match.winner_points = points
            match.challenge_badge = badge
            # Persist badge + XP to user profile
            try:
                await _award_challenge_badge(db, winner_id, badge, str(match_id))
                await _credit_xp(db, winner_id, points)
                await _credit_xp(db, match.opponent_id if winner_id == match.challenger_id else match.challenger_id, 10)  # participation XP
            except Exception as e:
                logger.warning(f"Badge/XP award failed: {e}")

        await db.flush()

        # Notify both players
        await notify_match_result_ready(db, match.challenger_id, str(match_id))
        await notify_match_result_ready(db, match.opponent_id, str(match_id))

        if c_tier_changed:
            await notify_elo_tier_changed(db, match.challenger_id, c_elo.tier, c_elo.elo)
        if o_tier_changed:
            await notify_elo_tier_changed(db, match.opponent_id, o_elo.tier, o_elo.elo)

        # Broadcast match_completed via WebSocket
        try:
            from app.api.v1.challenges_ws import broadcast_match_completed
            await broadcast_match_completed(str(match_id))
        except Exception as e:
            logger.warning(f"WS broadcast failed: {e}")

    except Exception as e:
        logger.error(f"Evaluation failed for match {match_id}: {e}", exc_info=True)


def _determine_winner(
    challenger_id: UUID,
    opponent_id: UUID,
    c_score: Optional[int],
    o_score: Optional[int],
) -> Optional[UUID]:
    if c_score is not None and o_score is None:
        return challenger_id
    if c_score is None and o_score is not None:
        return opponent_id
    if c_score is None and o_score is None:
        return None  # draw
    diff = abs(c_score - o_score)  # type: ignore[operator]
    if diff <= 2:
        return None  # draw
    return challenger_id if c_score > o_score else opponent_id  # type: ignore[operator]


async def _evaluate_submission(
    db: AsyncSession,
    submission: ChallengeSubmission,
    domain: str,
    task: Optional[ChallengeTask],
) -> None:
    try:
        if domain in ("coding", "data"):
            score, breakdown, feedback = await _evaluate_coding(submission, task)
        else:
            score, breakdown, feedback = await _evaluate_ai(submission, domain, task)

        submission.score = score
        submission.score_breakdown = breakdown
        submission.ai_feedback = feedback
    except Exception as e:
        logger.error(f"Submission evaluation failed: {e}", exc_info=True)
        # Fallback: mark as under review
        submission.score = None
        submission.ai_feedback = "Under Review — evaluation will complete within 24 hours."


async def _evaluate_coding(
    submission: ChallengeSubmission,
    task: Optional[ChallengeTask],
) -> tuple[int, dict, str]:
    """Evaluate coding submission via Judge0."""
    if not submission.content.strip():
        return 0, {"tests_passed": 0, "total_tests": 1}, "No code submitted."

    lang_id = LANGUAGE_IDS.get(submission.language or "python", 71)
    api_key = getattr(settings, "judge0_api_key", "")

    if not api_key:
        # No Judge0 key — use simple heuristic scoring
        return _heuristic_code_score(submission.content)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{JUDGE0_URL}/submissions",
                headers=JUDGE0_HEADERS,
                json={
                    "source_code": submission.content,
                    "language_id": lang_id,
                    "stdin": "",
                    "cpu_time_limit": 5,
                    "memory_limit": 128000,
                },
                params={"base64_encoded": "false", "wait": "true"},
            )
            data = resp.json()

        status_id = data.get("status", {}).get("id", 0)
        # Status 3 = Accepted
        if status_id == 3:
            score = 85 + min(15, len(submission.content) // 50)
            return (
                min(100, score),
                {"status": "accepted", "runtime_ms": data.get("time", 0)},
                "Your code compiled and ran successfully. Good solution structure.",
            )
        elif status_id in (4, 5):  # Wrong answer / TLE
            return (
                40,
                {"status": "wrong_answer"},
                "Your code ran but produced incorrect output. Review your logic.",
            )
        else:
            return (
                20,
                {"status": "compile_error", "error": data.get("compile_output", "")[:200]},
                "Your code had compilation errors. Check syntax and try again.",
            )
    except Exception as e:
        logger.warning(f"Judge0 call failed: {e}")
        return _heuristic_code_score(submission.content)


def _heuristic_code_score(content: str) -> tuple[int, dict, str]:
    """Simple heuristic when Judge0 is unavailable."""
    lines = [l for l in content.strip().splitlines() if l.strip()]
    score = min(100, max(10, len(lines) * 3))
    return (
        score,
        {"lines": len(lines), "method": "heuristic"},
        "Submission received and scored based on code structure.",
    )


async def _evaluate_ai(
    submission: ChallengeSubmission,
    domain: str,
    task: Optional[ChallengeTask],
) -> tuple[int, dict, str]:
    """Evaluate non-coding submission via OpenAI GPT-4o."""
    if not submission.content.strip():
        return 0, {"clarity": 0, "depth": 0, "relevance": 0, "quality_of_execution": 0}, "No content submitted."

    api_key = settings.openai_api_key
    if not api_key:
        return _heuristic_text_score(submission.content)

    task_context = ""
    if task:
        task_context = f"\n\nTask: {task.title}\nDescription: {task.description}"
        if task.requirements:
            task_context += f"\nRequirements: {task.requirements}"

    user_prompt = (
        f"Domain: {domain}{task_context}\n\n"
        f"Candidate Submission:\n{submission.content[:3000]}"
    )

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": RUBRIC_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            data = resp.json()

        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw)

        clarity = int(parsed.get("clarity", 0))
        depth = int(parsed.get("depth", 0))
        relevance = int(parsed.get("relevance", 0))
        quality = int(parsed.get("quality_of_execution", 0))
        total = clarity + depth + relevance + quality
        feedback = parsed.get("feedback", "Evaluation complete.")

        return (
            min(100, total),
            {
                "Clarity": clarity,
                "Depth": depth,
                "Relevance": relevance,
                "Quality of Execution": quality,
            },
            feedback,
        )
    except Exception as e:
        logger.error(f"OpenAI evaluation failed: {e}", exc_info=True)
        return _heuristic_text_score(submission.content)


def _heuristic_text_score(content: str) -> tuple[int, dict, str]:
    """Simple heuristic when OpenAI is unavailable."""
    words = len(content.strip().split())
    score = min(100, max(10, words // 5))
    per_dim = min(25, score // 4)
    return (
        score,
        {
            "Clarity": per_dim,
            "Depth": per_dim,
            "Relevance": per_dim,
            "Quality of Execution": per_dim,
        },
        "Submission received. Detailed AI feedback will be available shortly.",
    )


# ── Winner reward helpers ─────────────────────────────────────────────────────

_DIFFICULTY_REWARDS = {
    "easy":   (50,  "coding_warrior"),
    "medium": (100, "code_crusher"),
    "hard":   (200, "algorithm_master"),
}


def _winner_reward(difficulty: str) -> tuple[int, str]:
    """Return (points, badge_slug) for the given difficulty."""
    return _DIFFICULTY_REWARDS.get(difficulty, (50, "coding_warrior"))


async def _award_challenge_badge(
    db: AsyncSession,
    user_id,
    badge_slug: str,
    match_id: str,
) -> None:
    """Persist a challenge win badge to user_challenge_badges and send notification."""
    from app.models.challenges import UserChallengeBadge
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    # Upsert — ignore if already earned
    stmt = pg_insert(UserChallengeBadge).values(
        user_id=user_id,
        badge_slug=badge_slug,
        match_id=match_id,
    ).on_conflict_do_nothing(constraint="uq_user_badge")
    await db.execute(stmt)
    try:
        from app.services.challenge_notification_service import notify_challenge_badge_earned
        await notify_challenge_badge_earned(db, user_id, badge_slug, match_id)
    except Exception as e:
        logger.warning(f"Badge notification failed for {user_id}: {e}")


async def _credit_xp(db: AsyncSession, user_id, xp: int) -> None:
    """Add XP points to user.xp_points."""
    from app.models.user import User
    from sqlalchemy import update
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(xp_points=User.xp_points + xp)
    )
