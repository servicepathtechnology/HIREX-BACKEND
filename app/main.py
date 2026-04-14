"""HireX FastAPI application entry point — v5.1 Production."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.firebase import init_firebase
from app.core.database import engine
from app.api.v1.auth import router as auth_router
from app.api.v1.upload import router as upload_router
from app.api.v1.upload_presigned import router as presigned_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.submissions import router as submissions_router
from app.api.v1.bookmarks import router as bookmarks_router
from app.api.v1.profile import router as profile_router, router_scores, router_badges
from app.api.v1.recruiter_tasks import router as recruiter_tasks_router
from app.api.v1.recruiter_submissions import router as recruiter_submissions_router
from app.api.v1.pipeline import router as pipeline_router, candidate_pipeline_router
from app.api.v1.billing import router as billing_router
from app.api.v1.recruiter_analytics import router as analytics_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.recruiter_candidates import router as recruiter_candidates_router
from app.api.v1.ai_scoring import router as ai_scoring_router
from app.api.v1.messaging import router as messaging_router, ws_router
from app.api.v1.fcm import router as fcm_router
from app.api.v1.skill_scores import router as skill_scores_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.subscriptions import router as subscriptions_router, webhook_router
from app.api.v1.referrals import router as referrals_router
from app.api.v1.og_images import router as og_router
from app.admin.admin_router import router as admin_router
# Part 1 — 1v1 Live Challenges
from app.api.v1.candidates import router as candidates_router
from app.api.v1.challenges import router as challenges_router
from app.api.v1.challenges_ws import ws_challenges_router
# Part 2 — Solo Challenges (Daily/Weekly/Monthly)
from app.api.v1.solo_challenges_api import router as solo_challenges_router
# Part 3 — Leaderboards + Tiers
from app.api.leaderboard import router as leaderboard_router
from app.api.elo import router as elo_router
from app.api.seasons import router as seasons_router

logger = logging.getLogger(__name__)


def _init_sentry() -> None:
    dsn = getattr(settings, "sentry_dsn", "")
    if dsn and settings.app_env == "production":
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=dsn, environment=settings.app_env, traces_sample_rate=0.2)
            logger.info("Sentry initialized")
        except ImportError:
            logger.warning("sentry-sdk not installed, skipping Sentry init")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_sentry()
    init_firebase()
    async with engine.connect() as conn:
        await conn.execute(__import__('sqlalchemy').text("SELECT 1"))
    try:
        from backend.scoring.decay_scheduler import start_decay_scheduler
        start_decay_scheduler(app)
    except Exception as e:
        logger.warning(f"Decay scheduler not started: {e}")
    yield


app = FastAPI(
    title="HireX API",
    description="Execution-based hiring platform — v5.0 Production",
    version="5.0.0",
    lifespan=lifespan,
)

# Rate limiting (slowapi)
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from app.middleware.rate_limiter import limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
except ImportError:
    logger.warning("slowapi not installed, rate limiting disabled")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list if settings.app_env != "development" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Parts 1–4
app.include_router(auth_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(presigned_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(submissions_router, prefix="/api/v1")
app.include_router(bookmarks_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(router_scores, prefix="/api/v1")
app.include_router(router_badges, prefix="/api/v1")
app.include_router(recruiter_tasks_router, prefix="/api/v1")
app.include_router(recruiter_submissions_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(candidate_pipeline_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(recruiter_candidates_router, prefix="/api/v1")
app.include_router(ai_scoring_router, prefix="/api/v1")
app.include_router(messaging_router, prefix="/api/v1")
app.include_router(fcm_router, prefix="/api/v1")
app.include_router(skill_scores_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(ws_router)
# Part 5
app.include_router(subscriptions_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")
app.include_router(referrals_router, prefix="/api/v1")
app.include_router(og_router, prefix="/api/v1")
app.include_router(admin_router)
# Part 1 — 1v1 Live Challenges
app.include_router(candidates_router, prefix="/api/v1")
app.include_router(challenges_router, prefix="/api/v1")
app.include_router(ws_challenges_router)
# Part 2 — Solo Challenges
app.include_router(solo_challenges_router, prefix="/api/v1")
# Part 3 — Leaderboards + Tiers
app.include_router(leaderboard_router, prefix="/api/v1")
app.include_router(elo_router, prefix="/api/v1")
app.include_router(seasons_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "HireX API is running", "docs": "/docs"}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "environment": settings.app_env, "version": "5.1.0"}
