"""Add challenge_link to matches table.

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS challenge_link TEXT
    """))
    # Fix duration constraint to include 15 min (PRD allows 15, 30, 60)
    conn.execute(sa.text("""
        ALTER TABLE matches
        DROP CONSTRAINT IF EXISTS ck_matches_duration
    """))
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD CONSTRAINT ck_matches_duration
        CHECK (duration_minutes IN (15, 30, 60))
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE matches DROP COLUMN IF EXISTS challenge_link"))
    conn.execute(sa.text("ALTER TABLE matches DROP CONSTRAINT IF EXISTS ck_matches_duration"))
    conn.execute(sa.text("ALTER TABLE matches ADD CONSTRAINT ck_matches_duration CHECK (duration_minutes IN (30, 60))"))
