"""Add difficulty level to challenge_tasks and matches; update duration constraint.

Revision ID: 008
Revises: 007
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

_CREATE_ENUM = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
        CREATE TYPE {name} AS ENUM ({values});
    END IF;
END
$$;
"""


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create difficulty enum
    conn.execute(sa.text(_CREATE_ENUM.format(
        name="challenge_difficulty",
        values="'easy', 'medium', 'hard'"
    )))

    # 2. Add difficulty column to challenge_tasks
    conn.execute(sa.text("""
        ALTER TABLE challenge_tasks
        ADD COLUMN IF NOT EXISTS difficulty challenge_difficulty NOT NULL DEFAULT 'easy'
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_challenge_tasks_difficulty "
        "ON challenge_tasks(difficulty)"
    ))

    # 3. Add difficulty column to matches (records what level was chosen)
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS difficulty challenge_difficulty NOT NULL DEFAULT 'easy'
    """))

    # 4. Add decline_reason column to matches
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS decline_reason VARCHAR(100)
    """))

    # 5. Update duration constraint to allow 30, 60, 120 minutes
    conn.execute(sa.text("""
        ALTER TABLE matches DROP CONSTRAINT IF EXISTS ck_matches_duration
    """))
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD CONSTRAINT ck_matches_duration
        CHECK (duration_minutes IN (30, 60, 120))
    """))

    # 6. Add winner_points column to matches (points awarded to winner)
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS winner_points INTEGER DEFAULT 0
    """))

    # 7. Add challenge_badge column to matches (badge slug awarded)
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS challenge_badge VARCHAR(50)
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE matches DROP COLUMN IF EXISTS challenge_badge"))
    conn.execute(sa.text("ALTER TABLE matches DROP COLUMN IF EXISTS winner_points"))
    conn.execute(sa.text("ALTER TABLE matches DROP CONSTRAINT IF EXISTS ck_matches_duration"))
    conn.execute(sa.text("ALTER TABLE matches ADD CONSTRAINT ck_matches_duration CHECK (duration_minutes IN (15, 30, 60))"))
    conn.execute(sa.text("ALTER TABLE matches DROP COLUMN IF EXISTS decline_reason"))
    conn.execute(sa.text("ALTER TABLE matches DROP COLUMN IF EXISTS difficulty"))
    conn.execute(sa.text("ALTER TABLE challenge_tasks DROP COLUMN IF EXISTS difficulty"))
    conn.execute(sa.text("DROP TYPE IF EXISTS challenge_difficulty"))
