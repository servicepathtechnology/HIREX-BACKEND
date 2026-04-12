"""Add questions table (full PRD schema), user_badges, xp_points on users,
question_history, cancel status on matches.

Revision ID: 009
Revises: 008
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add xp_points to users
    conn.execute(sa.text("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS xp_points INTEGER NOT NULL DEFAULT 0
    """))

    # 2. Add 'cancelled' to match_status enum (challenger-initiated cancel)
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'cancelled'
                  AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'match_status')
            ) THEN
                ALTER TYPE match_status ADD VALUE 'cancelled';
            END IF;
        END
        $$
    """))

    # 3. Full questions table (PRD §7.5)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS questions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(200) NOT NULL,
            difficulty VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
            problem_statement TEXT NOT NULL,
            constraints TEXT,
            input_format TEXT,
            output_format TEXT,
            sample_input_1 TEXT,
            sample_output_1 TEXT,
            sample_input_2 TEXT,
            sample_output_2 TEXT,
            test_cases JSONB,
            time_limit_ms INTEGER NOT NULL DEFAULT 2000,
            memory_limit_mb INTEGER NOT NULL DEFAULT 256,
            editorial TEXT,
            tags TEXT[],
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_questions_diff ON questions(difficulty) WHERE is_active = true"
    ))

    # 4. Add question_id FK to matches (points to questions table)
    conn.execute(sa.text("""
        ALTER TABLE matches ADD COLUMN IF NOT EXISTS question_id UUID REFERENCES questions(id) ON DELETE SET NULL
    """))

    # 5. question_history table (PRD §7.6)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS question_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
            seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_qhistory_user ON question_history(user_id, seen_at)"
    ))

    # 6. badges table (PRD §7.8)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS challenge_badges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            icon_url TEXT,
            condition JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    # 7. user_badges table (PRD §7.9)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_challenge_badges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            badge_slug VARCHAR(50) NOT NULL,
            match_id UUID REFERENCES matches(id) ON DELETE SET NULL,
            earned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_badge UNIQUE (user_id, badge_slug)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_challenge_badges(user_id)"
    ))

    # 8. Seed badge definitions — use dollar-quoted strings to avoid SQLAlchemy
    #    treating colons inside JSON as bind parameters
    conn.execute(sa.text("""
        INSERT INTO challenge_badges (slug, name, description, condition)
        VALUES
          ('coding_warrior',   'Coding Warrior',   'Won an Easy 1v1 coding challenge',    '{"type":"win_difficulty","difficulty":"easy"}'::jsonb),
          ('code_crusher',     'Code Crusher',     'Won a Medium 1v1 coding challenge',   '{"type":"win_difficulty","difficulty":"medium"}'::jsonb),
          ('algorithm_master', 'Algorithm Master', 'Won a Hard 1v1 coding challenge',     '{"type":"win_difficulty","difficulty":"hard"}'::jsonb),
          ('first_blood',      'First Blood',      'Won your very first 1v1 challenge',   '{"type":"first_win"}'::jsonb),
          ('win_streak_3',     'Hat Trick',        '3 consecutive 1v1 wins',              '{"type":"win_streak","threshold":3}'::jsonb),
          ('win_streak_5',     'Unstoppable',      '5 consecutive 1v1 wins',              '{"type":"win_streak","threshold":5}'::jsonb),
          ('speed_demon',      'Speed Demon',      'Won with >80 pct score in under 10 min', '{"type":"speed_win","score_threshold":80,"time_threshold_sec":600}'::jsonb),
          ('domain_master',    'Domain Master',    '10 total wins in coding',             '{"type":"total_wins","threshold":10}'::jsonb)
        ON CONFLICT (slug) DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS user_challenge_badges CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS challenge_badges CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS question_history CASCADE"))
    conn.execute(sa.text("ALTER TABLE matches DROP COLUMN IF EXISTS question_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS questions CASCADE"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS xp_points"))
