"""Skill score seeding and computation logic."""

from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import CandidateProfile
from app.models.task import SkillScoreHistory

# Map skill tags to domains
SKILL_DOMAIN_MAP = {
    # Engineering
    "python": "engineering", "javascript": "engineering", "typescript": "engineering",
    "dart": "engineering", "flutter": "engineering", "react": "engineering",
    "node.js": "engineering", "java": "engineering", "go": "engineering",
    "rust": "engineering", "c++": "engineering", "sql": "engineering",
    "postgresql": "engineering", "mongodb": "engineering", "redis": "engineering",
    "aws": "engineering", "docker": "engineering", "kubernetes": "engineering",
    "fastapi": "engineering", "django": "engineering", "rest api": "engineering",
    "graphql": "engineering", "machine learning": "engineering", "data science": "engineering",
    # Design
    "figma": "design", "ui design": "design", "ux design": "design",
    "product design": "design", "graphic design": "design", "branding": "design",
    "prototyping": "design", "user research": "design", "wireframing": "design",
    # Product
    "product management": "product", "product strategy": "product",
    "roadmapping": "product", "user stories": "product", "agile": "product",
    "scrum": "product", "okrs": "product", "metrics": "product",
    # Business
    "business analysis": "business", "market research": "business",
    "financial modeling": "business", "strategy": "business",
    "consulting": "business", "operations": "business",
    # Marketing
    "digital marketing": "marketing", "seo": "marketing", "content marketing": "marketing",
    "social media": "marketing", "growth hacking": "marketing", "copywriting": "marketing",
    # Writing
    "technical writing": "writing", "blog writing": "writing",
    "documentation": "writing", "content creation": "writing",
}


def map_skill_to_domain(skill: str) -> str:
    return SKILL_DOMAIN_MAP.get(skill.lower(), "engineering")


async def seed_skill_scores(candidate_id, db: AsyncSession) -> None:
    """Seed initial skill scores from onboarding skill tags."""
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == candidate_id)
    )
    profile = result.scalar_one_or_none()
    if not profile or not profile.skill_tags:
        return

    # Check if already seeded
    existing = await db.execute(
        select(SkillScoreHistory).where(
            SkillScoreHistory.candidate_id == candidate_id,
            SkillScoreHistory.reason == "Initial skill declaration",
        )
    )
    if existing.scalar_one_or_none():
        return  # Already seeded

    domain_scores: Dict[str, int] = {}
    for skill in profile.skill_tags:
        domain = map_skill_to_domain(skill)
        domain_scores[domain] = min(domain_scores.get(domain, 0) + 100, 300)

    overall = int(sum(domain_scores.values()) / max(len(domain_scores), 1))

    # Write history entries
    for domain, score in domain_scores.items():
        history = SkillScoreHistory(
            candidate_id=candidate_id,
            domain=domain,
            score=score,
            delta=score,
            reason="Initial skill declaration",
        )
        db.add(history)

    # Update profile
    profile.skill_score = overall
    profile.scores = domain_scores
    await db.flush()


async def get_skill_scores(candidate_id, db: AsyncSession) -> dict:
    """Get full skill score breakdown for a candidate."""
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == candidate_id)
    )
    profile = result.scalar_one_or_none()

    history_result = await db.execute(
        select(SkillScoreHistory)
        .where(SkillScoreHistory.candidate_id == candidate_id)
        .order_by(SkillScoreHistory.created_at.desc())
        .limit(20)
    )
    history = history_result.scalars().all()

    domains = profile.scores if profile and profile.scores else {}
    overall = profile.skill_score if profile else 0

    # Compute percentile (simplified — based on overall score out of 1000)
    percentile = min(round((overall / 1000) * 100, 1), 99.9)

    return {
        "overall": overall,
        "domains": domains,
        "percentile": percentile,
        "history": history,
    }
