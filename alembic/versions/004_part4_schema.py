"""Part 4 schema — ai_scoring_jobs, message_threads, messages, fcm_tokens,
skill_score_snapshots, recommendation_signals.
Also adds content_hash to submissions and notification_prefs to users.

Revision ID: 004
Revises: 003
Create Date: 2026-04-08
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_job_status') THEN
                CREATE TYPE ai_job_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'skipped');
            END IF;
        END
        $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fcm_platform') THEN
                CREATE TYPE fcm_platform AS ENUM ('android', 'ios');
            END IF;
        END
        $$
    """)

    # ai_scoring_jobs
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_scoring_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            submission_id UUID NOT NULL REFERENCES submissions(id),
            task_id UUID NOT NULL REFERENCES tasks(id),
            status ai_job_status NOT NULL DEFAULT 'queued',
            model_used VARCHAR(60),
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            ai_scores JSONB,
            ai_total_score FLOAT,
            ai_summary TEXT,
            ai_flags JSONB,
            recruiter_approved BOOLEAN,
            recruiter_overrides JSONB,
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            completed_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_scoring_jobs_submission_id ON ai_scoring_jobs (submission_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_scoring_jobs_status ON ai_scoring_jobs (status)")

    # message_threads
    op.execute("""
        CREATE TABLE IF NOT EXISTS message_threads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recruiter_id UUID NOT NULL REFERENCES users(id),
            candidate_id UUID NOT NULL REFERENCES users(id),
            task_id UUID NOT NULL REFERENCES tasks(id),
            last_message_at TIMESTAMP,
            last_message_preview VARCHAR(200),
            recruiter_unread_count INTEGER NOT NULL DEFAULT 0,
            candidate_unread_count INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT uq_message_threads_recruiter_candidate_task UNIQUE (recruiter_id, candidate_id, task_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_message_threads_recruiter_id ON message_threads (recruiter_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_message_threads_candidate_id ON message_threads (candidate_id)")

    # messages
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            thread_id UUID NOT NULL REFERENCES message_threads(id),
            sender_id UUID NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            is_read BOOLEAN NOT NULL DEFAULT false,
            read_at TIMESTAMP,
            is_deleted_by_sender BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_thread_id ON messages (thread_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_sender_id ON messages (sender_id)")

    # fcm_tokens
    op.execute("""
        CREATE TABLE IF NOT EXISTS fcm_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            token TEXT NOT NULL,
            platform fcm_platform NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_used_at TIMESTAMP NOT NULL DEFAULT now(),
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT uq_fcm_tokens_token UNIQUE (token)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_fcm_tokens_user_id ON fcm_tokens (user_id)")

    # skill_score_snapshots
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_score_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES users(id),
            overall_score INTEGER NOT NULL,
            domain_scores JSONB NOT NULL,
            percentile_overall FLOAT NOT NULL,
            percentile_by_domain JSONB NOT NULL,
            snapshot_reason VARCHAR(200) NOT NULL,
            submission_id UUID REFERENCES submissions(id),
            hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_skill_score_snapshots_candidate_id ON skill_score_snapshots (candidate_id)")

    # recommendation_signals
    op.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_signals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES users(id),
            task_id UUID NOT NULL REFERENCES tasks(id),
            signal_type VARCHAR(60) NOT NULL,
            signal_weight FLOAT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendation_signals_candidate_id ON recommendation_signals (candidate_id)")

    # Add content_hash to submissions
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='submissions' AND column_name='content_hash'
            ) THEN
                ALTER TABLE submissions ADD COLUMN content_hash VARCHAR(64);
            END IF;
        END
        $$
    """)

    # Add notification_prefs to users
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='notification_prefs'
            ) THEN
                ALTER TABLE users ADD COLUMN notification_prefs JSONB;
            END IF;
        END
        $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendation_signals")
    op.execute("DROP TABLE IF EXISTS skill_score_snapshots")
    op.execute("DROP TABLE IF EXISTS fcm_tokens")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS message_threads")
    op.execute("DROP TABLE IF EXISTS ai_scoring_jobs")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS content_hash")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS notification_prefs")
    op.execute("DROP TYPE IF EXISTS fcm_platform")
    op.execute("DROP TYPE IF EXISTS ai_job_status")
