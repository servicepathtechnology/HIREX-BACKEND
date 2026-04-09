"""Part 5 schema — subscriptions, referrals, admin, rate limiting columns."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Subscription columns on recruiter_profiles ────────────────────────────
    op.add_column("recruiter_profiles", sa.Column("subscription_plan", sa.String(30), nullable=True))
    op.add_column("recruiter_profiles", sa.Column("subscription_status", sa.String(30), nullable=True))
    op.add_column("recruiter_profiles", sa.Column("subscription_id", sa.String(100), nullable=True))
    op.add_column("recruiter_profiles", sa.Column("subscription_valid_until", sa.DateTime, nullable=True))
    op.add_column("recruiter_profiles", sa.Column("active_task_limit", sa.Integer, nullable=True))

    # ── Referral columns on users ─────────────────────────────────────────────
    op.add_column("users", sa.Column("referral_code", sa.String(12), nullable=True, unique=True))
    op.add_column("users", sa.Column("referred_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("users", sa.Column("is_suspended", sa.Boolean, server_default="false", nullable=False))

    # ── Referral rewards table ────────────────────────────────────────────────
    op.create_table(
        "referral_rewards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("referrer_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("referred_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reward_type", sa.String(60), nullable=False),
        sa.Column("reward_value", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("issued_at", sa.DateTime, nullable=True),
    )

    # ── Admin users table ─────────────────────────────────────────────────────
    op.create_table(
        "admin_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # ── Admin audit log table ─────────────────────────────────────────────────
    op.create_table(
        "admin_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("admin_email", sa.String(255), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(60), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # ── Performance indexes ───────────────────────────────────────────────────
    op.create_index("ix_tasks_recruiter_id", "tasks", ["recruiter_id"])
    op.create_index("ix_submissions_task_id", "submissions", ["task_id"])
    op.create_index("ix_submissions_candidate_id", "submissions", ["candidate_id"])
    op.create_index("ix_pipeline_entries_recruiter_id", "pipeline_entries", ["recruiter_id"])
    op.create_index("ix_submissions_task_status", "submissions", ["task_id", "status"])
    op.create_index("ix_tasks_published_active_deadline", "tasks", ["is_published", "is_active", "deadline"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read", "created_at"])
    op.create_index("ix_users_referral_code", "users", ["referral_code"])


def downgrade() -> None:
    op.drop_index("ix_users_referral_code")
    op.drop_index("ix_notifications_user_read")
    op.drop_index("ix_tasks_published_active_deadline")
    op.drop_index("ix_submissions_task_status")
    op.drop_index("ix_pipeline_entries_recruiter_id")
    op.drop_index("ix_submissions_candidate_id")
    op.drop_index("ix_submissions_task_id")
    op.drop_index("ix_tasks_recruiter_id")
    op.drop_table("admin_audit_log")
    op.drop_table("admin_users")
    op.drop_table("referral_rewards")
    op.drop_column("users", "is_suspended")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
    op.drop_column("recruiter_profiles", "active_task_limit")
    op.drop_column("recruiter_profiles", "subscription_valid_until")
    op.drop_column("recruiter_profiles", "subscription_id")
    op.drop_column("recruiter_profiles", "subscription_status")
    op.drop_column("recruiter_profiles", "subscription_plan")
