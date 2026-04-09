"""Part 3 schema — task_payments, pipeline_entries, notifications, recruiter_analytics.
Also adds tier column to tasks.

Revision ID: 003
Revises: 002
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
                CREATE TYPE payment_status AS ENUM ('pending', 'paid', 'failed', 'refunded');
            END IF;
        END
        $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_stage') THEN
                CREATE TYPE pipeline_stage AS ENUM ('shortlisted', 'interviewing', 'offer_sent', 'hired', 'rejected');
            END IF;
        END
        $$
    """)

    # Add tier column to tasks
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='tasks' AND column_name='tier'
            ) THEN
                ALTER TABLE tasks ADD COLUMN tier VARCHAR(20) NOT NULL DEFAULT 'standard';
            END IF;
        END
        $$
    """)

    # task_payments
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_payments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recruiter_id UUID NOT NULL REFERENCES users(id),
            task_id UUID NOT NULL REFERENCES tasks(id),
            razorpay_order_id VARCHAR(100) UNIQUE NOT NULL,
            razorpay_payment_id VARCHAR(100),
            razorpay_signature VARCHAR(300),
            amount_paise INTEGER NOT NULL,
            currency VARCHAR(10) DEFAULT 'INR',
            status payment_status NOT NULL DEFAULT 'pending',
            tier VARCHAR(40) NOT NULL,
            paid_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_payments_recruiter_id ON task_payments (recruiter_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_payments_task_id ON task_payments (task_id)")

    # pipeline_entries
    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recruiter_id UUID NOT NULL REFERENCES users(id),
            candidate_id UUID NOT NULL REFERENCES users(id),
            task_id UUID NOT NULL REFERENCES tasks(id),
            submission_id UUID NOT NULL REFERENCES submissions(id),
            stage pipeline_stage NOT NULL DEFAULT 'shortlisted',
            recruiter_notes TEXT,
            stage_updated_at TIMESTAMP NOT NULL DEFAULT now(),
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT uq_pipeline_recruiter_candidate_task UNIQUE (recruiter_id, candidate_id, task_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pipeline_entries_recruiter_id ON pipeline_entries (recruiter_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pipeline_entries_stage ON pipeline_entries (stage)")

    # notifications
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            type VARCHAR(80) NOT NULL,
            title VARCHAR(160) NOT NULL,
            body TEXT NOT NULL,
            data JSONB,
            is_read BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read)")

    # recruiter_analytics
    op.execute("""
        CREATE TABLE IF NOT EXISTS recruiter_analytics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID NOT NULL REFERENCES tasks(id) UNIQUE,
            total_views INTEGER DEFAULT 0,
            total_submissions INTEGER DEFAULT 0,
            scored_count INTEGER DEFAULT 0,
            shortlisted_count INTEGER DEFAULT 0,
            hired_count INTEGER DEFAULT 0,
            avg_score FLOAT,
            score_distribution JSONB,
            avg_time_spent_mins FLOAT,
            time_to_first_submission_hours FLOAT,
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_recruiter_analytics_task_id ON recruiter_analytics (task_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recruiter_analytics")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS pipeline_entries")
    op.execute("DROP TABLE IF EXISTS task_payments")
    op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS tier")
    op.execute("DROP TYPE IF EXISTS pipeline_stage")
    op.execute("DROP TYPE IF EXISTS payment_status")
