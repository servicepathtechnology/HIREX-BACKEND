# Models package — import all models so Alembic can detect them
from app.models.user import User, CandidateProfile, RecruiterProfile  # noqa: F401
from app.models.task import Task, Submission, Bookmark, SkillScoreHistory  # noqa: F401
from app.models.recruiter import TaskPayment, PipelineEntry, Notification, RecruiterAnalytics  # noqa: F401
