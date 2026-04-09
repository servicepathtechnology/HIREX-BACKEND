"""Part 2 schema — tasks, submissions, bookmarks, skill_score_history.
Also adds scores JSONB column to candidate_profiles.

Revision ID: 002
Revises: 001
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums — safe if already exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_difficulty') THEN
                CREATE TYPE task_difficulty AS ENUM ('beginner', 'intermediate', 'advanced', 'expert');
            END IF;
        END
        $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_type_enum') THEN
                CREATE TYPE task_type_enum AS ENUM ('code', 'design', 'case_study', 'business', 'product', 'writing');
            END IF;
        END
        $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'submission_status') THEN
                CREATE TYPE submission_status AS ENUM ('draft', 'submitted', 'under_review', 'scored', 'rejected');
            END IF;
        END
        $$
    """)

    # tasks
    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            recruiter_id UUID NOT NULL REFERENCES users(id),
            title VARCHAR(160) NOT NULL,
            slug VARCHAR(180) UNIQUE NOT NULL,
            description TEXT NOT NULL,
            problem_statement TEXT NOT NULL,
            evaluation_criteria JSONB NOT NULL,
            domain VARCHAR(60) NOT NULL,
            difficulty task_difficulty NOT NULL,
            task_type task_type_enum NOT NULL,
            submission_types VARCHAR[] NOT NULL,
            max_file_size_mb INTEGER DEFAULT 10,
            allowed_file_types VARCHAR[],
            deadline TIMESTAMP NOT NULL,
            max_submissions INTEGER,
            is_published BOOLEAN DEFAULT false,
            is_active BOOLEAN DEFAULT true,
            skills_tested VARCHAR[] NOT NULL,
            estimated_hours FLOAT,
            company_visible BOOLEAN DEFAULT false,
            company_name VARCHAR(120),
            prize_or_opportunity TEXT,
            view_count INTEGER DEFAULT 0,
            submission_count INTEGER DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_domain ON tasks (domain)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_difficulty ON tasks (difficulty)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_is_active ON tasks (is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_deadline ON tasks (deadline)")

    # submissions
    op.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID NOT NULL REFERENCES tasks(id),
            candidate_id UUID NOT NULL REFERENCES users(id),
            status submission_status NOT NULL DEFAULT 'draft',
            text_content TEXT,
            code_content TEXT,
            code_language VARCHAR(40),
            file_urls VARCHAR[],
            link_url TEXT,
            recording_url TEXT,
            notes TEXT,
            submitted_at TIMESTAMP,
            score_accuracy FLOAT,
            score_approach FLOAT,
            score_completeness FLOAT,
            score_efficiency FLOAT,
            total_score FLOAT,
            rank INTEGER,
            percentile FLOAT,
            recruiter_feedback TEXT,
            ai_summary TEXT,
            time_spent_minutes INTEGER,
            is_shortlisted BOOLEAN DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT uq_submissions_task_candidate UNIQUE (task_id, candidate_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_candidate_id ON submissions (candidate_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_submissions_task_id ON submissions (task_id)")

    # bookmarks
    op.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES users(id),
            task_id UUID NOT NULL REFERENCES tasks(id),
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT uq_bookmarks_candidate_task UNIQUE (candidate_id, task_id)
        )
    """)

    # skill_score_history
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_score_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL REFERENCES users(id),
            domain VARCHAR(60) NOT NULL,
            score INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            reason VARCHAR(200) NOT NULL,
            submission_id UUID REFERENCES submissions(id),
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_skill_score_history_candidate_id ON skill_score_history (candidate_id)")

    # Add columns to candidate_profiles if they don't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='candidate_profiles' AND column_name='scores'
            ) THEN
                ALTER TABLE candidate_profiles ADD COLUMN scores JSONB;
            END IF;
        END
        $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='candidate_profiles' AND column_name='public_profile'
            ) THEN
                ALTER TABLE candidate_profiles ADD COLUMN public_profile BOOLEAN DEFAULT true;
            END IF;
        END
        $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS skill_score_history")
    op.execute("DROP TABLE IF EXISTS bookmarks")
    op.execute("DROP TABLE IF EXISTS submissions")
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("DROP TYPE IF EXISTS submission_status")
    op.execute("DROP TYPE IF EXISTS task_type_enum")
    op.execute("DROP TYPE IF EXISTS task_difficulty")
    op.execute("ALTER TABLE candidate_profiles DROP COLUMN IF EXISTS public_profile")
    op.execute("ALTER TABLE candidate_profiles DROP COLUMN IF EXISTS scores")
