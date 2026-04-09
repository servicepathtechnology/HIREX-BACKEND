"""Decay scheduler — runs daily at 02:00 UTC via APScheduler."""

import hashlib
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import CandidateProfile
from app.models.part4 import SkillScoreSnapshot

logger = logging.getLogger(__name__)

DECAY_RATE = 0.02  # 2% per 30 days
DECAY_FLOOR = 100
INACTIVITY_DAYS = 30
BATCH_SIZE = 500


async def run_decay(db: AsyncSession) -> int:
    """Apply inactivity decay to all candidates. Returns number of candidates updated."""
    cutoff = datetime.utcnow() - timedelta(days=INACTIVITY_DAYS)
    updated = 0

    # Process in batches
    offset = 0
    while True:
        result = await db.execute(
            select(CandidateProfile).offset(offset).limit(BATCH_SIZE)
        )
        profiles = result.scalars().all()
        if not profiles:
            break

        for profile in profiles:
            domain_scores: dict = dict(profile.scores or {})
            if not domain_scores:
                continue

            changed = False
            for domain, score in list(domain_scores.items()):
                # Check last snapshot for this domain
                snap_result = await db.execute(
                    select(SkillScoreSnapshot)
                    .where(
                        SkillScoreSnapshot.candidate_id == profile.user_id,
                        SkillScoreSnapshot.domain_scores.op("?")(domain),
                    )
                    .order_by(SkillScoreSnapshot.created_at.desc())
                    .limit(1)
                )
                last_snap = snap_result.scalar_one_or_none()

                if last_snap and last_snap.created_at > cutoff:
                    continue  # Active in this domain — skip decay

                if score <= DECAY_FLOOR:
                    continue  # Already at floor

                decay_amount = max(1, round(score * DECAY_RATE))
                new_score = max(DECAY_FLOOR, score - decay_amount)
                domain_scores[domain] = new_score
                changed = True

            if not changed:
                continue

            new_overall = round(sum(domain_scores.values()) / len(domain_scores))
            new_overall = max(0, min(1000, new_overall))

            now_str = datetime.utcnow().isoformat()
            snap_hash = hashlib.sha256(
                json.dumps(
                    {
                        "candidate_id": str(profile.user_id),
                        "overall_score": new_overall,
                        "domain_scores": domain_scores,
                        "created_at": now_str,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()

            snapshot = SkillScoreSnapshot(
                candidate_id=profile.user_id,
                overall_score=new_overall,
                domain_scores=domain_scores,
                percentile_overall=round((new_overall / 1000) * 100, 1),
                percentile_by_domain={d: round((s / 1000) * 100, 1) for d, s in domain_scores.items()},
                snapshot_reason=f"Inactivity decay — {INACTIVITY_DAYS} days since last task",
                hash=snap_hash,
            )
            db.add(snapshot)

            profile.skill_score = new_overall
            profile.scores = domain_scores
            updated += 1

        await db.flush()
        offset += BATCH_SIZE

    logger.info(f"Decay run complete. {updated} candidates updated.")
    return updated


def start_decay_scheduler(app) -> None:
    """Start APScheduler decay job on FastAPI startup."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.core.database import AsyncSessionLocal

    scheduler = AsyncIOScheduler(timezone="UTC")

    async def _decay_job():
        async with AsyncSessionLocal() as db:
            async with db.begin():
                count = await run_decay(db)
                logger.info(f"Scheduled decay run: {count} candidates updated")

    scheduler.add_job(_decay_job, "cron", hour=2, minute=0)
    scheduler.start()
    logger.info("Decay scheduler started — runs daily at 02:00 UTC")
