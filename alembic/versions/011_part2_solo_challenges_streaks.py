"""Part 2 — Daily/Weekly/Monthly Challenges + Streaks + User Preferences.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. daily_challenges — one row per calendar day (shared across all users)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS daily_challenges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            challenge_date DATE UNIQUE NOT NULL,
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_daily_challenges_date ON daily_challenges(challenge_date)"
    ))

    # 2. weekly_challenges — one row per ISO calendar week
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS weekly_challenges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            year INTEGER NOT NULL,
            week_number INTEGER NOT NULL,
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_weekly_year_week UNIQUE (year, week_number)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_weekly_challenges_week ON weekly_challenges(year, week_number)"
    ))

    # 3. monthly_challenges — one row per calendar month
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS monthly_challenges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_monthly_year_month UNIQUE (year, month)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_monthly_challenges_mon ON monthly_challenges(year, month)"
    ))

    # 4. user_challenges — each user's attempt at a daily/weekly/monthly challenge
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_challenges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            challenge_type VARCHAR(10) NOT NULL CHECK (challenge_type IN ('daily','weekly','monthly')),
            challenge_ref_id UUID NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'not_started'
                CHECK (status IN ('not_started','in_progress','completed','failed')),
            started_at TIMESTAMPTZ,
            submitted_at TIMESTAMPTZ,
            room_token TEXT,
            room_url TEXT,
            score INTEGER CHECK (score >= 0 AND score <= 100),
            tests_passed INTEGER,
            tests_total INTEGER,
            result_status VARCHAR(30),
            time_taken_sec INTEGER,
            xp_earned INTEGER DEFAULT 0,
            language VARCHAR(20),
            code_content TEXT,
            error_message TEXT,
            judge_job_ids TEXT[],
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_challenge_dedup UNIQUE (user_id, challenge_type, challenge_ref_id)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_user_challenges_user ON user_challenges(user_id, challenge_type)"
    ))

    # 5. user_streaks — one row per user
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_streaks (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            current_streak INTEGER NOT NULL DEFAULT 0,
            longest_streak INTEGER NOT NULL DEFAULT 0,
            last_activity_date DATE,
            grace_day_available BOOLEAN NOT NULL DEFAULT true,
            grace_day_used_date DATE,
            streak_started_date DATE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    # 6. streak_history — log of every streak event
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS streak_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_date DATE NOT NULL,
            event_type VARCHAR(20) NOT NULL
                CHECK (event_type IN ('attempted','completed','missed','grace_used','streak_broken','milestone')),
            streak_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_streak_history_user ON streak_history(user_id, event_date DESC)"
    ))

    # 7. user_preferences — scheduling preferences
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            weekly_day VARCHAR(10)
                CHECK (weekly_day IN ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')),
            monthly_date INTEGER CHECK (monthly_date >= 1 AND monthly_date <= 28),
            notification_time VARCHAR(5) NOT NULL DEFAULT '09:00',
            timezone VARCHAR(60) NOT NULL DEFAULT 'UTC',
            notifications_enabled BOOLEAN NOT NULL DEFAULT true,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    # 8. question_schedule_history — prevents question repeats
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS question_schedule_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            challenge_type VARCHAR(10) NOT NULL CHECK (challenge_type IN ('daily','weekly','monthly')),
            used_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_q_schedule_history ON question_schedule_history(challenge_type, used_date DESC)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS question_schedule_history CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS user_preferences CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS streak_history CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS user_streaks CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS user_challenges CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS monthly_challenges CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS weekly_challenges CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS daily_challenges CASCADE"))
