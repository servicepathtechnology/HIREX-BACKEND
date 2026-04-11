"""Part 1 — 1v1 Live Challenges schema.

Creates: challenge_tasks, matches, challenge_submissions, user_elo
Seeds: 11 challenge tasks across all 6 domains
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

# Helper: create a PG enum only if it doesn't already exist
_CREATE_ENUM = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
        CREATE TYPE {name} AS ENUM ({values});
    END IF;
END
$$;
"""


def _enum_sql(name: str, values: list[str]) -> str:
    vals = ", ".join(f"'{v}'" for v in values)
    return _CREATE_ENUM.format(name=name, values=vals)


def upgrade() -> None:
    conn = op.get_bind()

    # ── Enums (idempotent) ────────────────────────────────────────────────────
    conn.execute(sa.text(_enum_sql(
        "challenge_domain",
        ["coding", "design", "product", "marketing", "data", "writing"]
    )))
    conn.execute(sa.text(_enum_sql(
        "match_status",
        ["pending", "active", "completed", "cancelled", "expired"]
    )))
    conn.execute(sa.text(_enum_sql(
        "elo_tier",
        ["bronze", "silver", "gold", "platinum", "diamond", "elite"]
    )))

    # ── challenge_tasks ───────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS challenge_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain challenge_domain NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            requirements TEXT,
            evaluation_criteria JSONB,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_challenge_tasks_domain "
        "ON challenge_tasks(domain)"
    ))

    # ── matches ───────────────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS matches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            challenger_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            opponent_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            domain challenge_domain NOT NULL,
            task_id UUID REFERENCES challenge_tasks(id) ON DELETE SET NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 30
                CONSTRAINT ck_matches_duration CHECK (duration_minutes IN (15, 30, 60)),
            status match_status NOT NULL DEFAULT 'pending',
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            winner_id UUID REFERENCES users(id) ON DELETE SET NULL,
            challenger_elo_before INTEGER NOT NULL DEFAULT 1000,
            opponent_elo_before INTEGER NOT NULL DEFAULT 1000,
            challenger_elo_after INTEGER,
            opponent_elo_after INTEGER,
            invite_message VARCHAR(200),
            spectator_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_matches_challenger_id ON matches(challenger_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_matches_opponent_id ON matches(opponent_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_matches_status ON matches(status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_matches_created_at ON matches(created_at)"
    ))

    # ── challenge_submissions ─────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS challenge_submissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL DEFAULT '',
            language VARCHAR(40),
            submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
            score INTEGER,
            score_breakdown JSONB,
            ai_feedback TEXT,
            is_auto BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_challenge_submission_match_user UNIQUE (match_id, user_id)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_challenge_submissions_match_id "
        "ON challenge_submissions(match_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_challenge_submissions_user_id "
        "ON challenge_submissions(user_id)"
    ))

    # ── user_elo ──────────────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_elo (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            elo INTEGER NOT NULL DEFAULT 1000,
            tier elo_tier NOT NULL DEFAULT 'silver',
            matches_played INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            draws INTEGER NOT NULL DEFAULT 0,
            peak_elo INTEGER NOT NULL DEFAULT 1000,
            current_streak INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    # ── Seed challenge tasks (only if table is empty) ─────────────────────────
    conn.execute(sa.text("""
        INSERT INTO challenge_tasks (domain, title, description, requirements, is_active, created_at)
        SELECT v.domain::challenge_domain, v.title, v.description, v.requirements, true, NOW()
        FROM (VALUES
            ('coding', 'Two Sum',
             'Given an array of integers and a target, return indices of the two numbers that add up to target.',
             'Each input has exactly one solution. You may not use the same element twice.'),
            ('coding', 'Reverse a Linked List',
             'Given the head of a singly linked list, reverse the list and return the reversed list.',
             'Implement an iterative solution. Time complexity must be O(n).'),
            ('coding', 'Valid Parentheses',
             'Given a string containing only brackets, determine if the input string is valid.',
             'Open brackets must be closed by the same type and in the correct order.'),
            ('design', 'Mobile Onboarding Flow',
             'Design a 3-screen onboarding flow for a fintech mobile app targeting first-time investors.',
             'Include: welcome screen, value proposition, and account setup. Focus on clarity and trust.'),
            ('design', 'E-commerce Product Page Redesign',
             'Redesign the product detail page for a fashion e-commerce app to improve conversion.',
             'Include: image gallery, size selector, reviews, and add-to-cart CTA. Mobile-first.'),
            ('product', 'Improve Retention for a Streaming App',
             'A streaming app has 40% D7 retention. Propose a product strategy to improve it to 60% in 3 months.',
             'Include: problem diagnosis, proposed features, success metrics, and tradeoffs.'),
            ('product', 'Design a Notification System',
             'Design the notification system for a social media platform with 10M daily active users.',
             'Cover: notification types, delivery channels, user preferences, and technical architecture.'),
            ('marketing', 'Launch Campaign for a B2B SaaS Tool',
             'Create a go-to-market campaign for a new project management SaaS targeting SMBs.',
             'Include: target audience, key messages, channels, and a 30-day launch plan.'),
            ('data', 'Sales Funnel Analysis',
             'Given a dataset of user events (signup, trial_start, upgrade, churn), calculate conversion rates.',
             'Write SQL queries to compute: signup-to-trial rate, trial-to-paid rate, and monthly churn rate.'),
            ('data', 'Cohort Retention Analysis',
             'Write a SQL query to compute weekly cohort retention for users who signed up in the last 8 weeks.',
             'Output: cohort_week, week_number, users_retained, retention_rate.'),
            ('writing', 'Product Announcement Blog Post',
             'Write a 300-400 word blog post announcing a new AI-powered feature for a productivity app.',
             'Tone: professional but approachable. Include: headline, problem, feature description, and CTA.')
        ) AS v(domain, title, description, requirements)
        WHERE NOT EXISTS (SELECT 1 FROM challenge_tasks LIMIT 1)
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS user_elo CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS challenge_submissions CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS matches CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS challenge_tasks CASCADE"))
    conn.execute(sa.text("DROP TYPE IF EXISTS elo_tier"))
    conn.execute(sa.text("DROP TYPE IF EXISTS match_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS challenge_domain"))
