"""Part 1 — 1v1 Live Challenges schema.

Creates: challenge_tasks, matches, challenge_submissions, user_elo
Seeds: 10 challenge tasks across all 6 domains
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums (idempotent) ────────────────────────────────────────────────────
    op.execute(
        "DO $body$ BEGIN "
        "CREATE TYPE challenge_domain AS ENUM "
        "('coding','design','product','marketing','data','writing'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $body$;"
    )
    op.execute(
        "DO $body$ BEGIN "
        "CREATE TYPE match_status AS ENUM "
        "('pending','active','completed','cancelled','expired'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $body$;"
    )
    op.execute(
        "DO $body$ BEGIN "
        "CREATE TYPE elo_tier AS ENUM "
        "('bronze','silver','gold','platinum','diamond','elite'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $body$;"
    )

    # ── challenge_tasks ───────────────────────────────────────────────────────
    op.create_table(
        "challenge_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "domain",
            sa.Enum("coding", "design", "product", "marketing", "data", "writing",
                    name="challenge_domain", create_type=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("requirements", sa.Text, nullable=True),
        sa.Column("evaluation_criteria", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_challenge_tasks_domain", "challenge_tasks", ["domain"])

    # ── matches ───────────────────────────────────────────────────────────────
    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("challenger_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opponent_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "domain",
            sa.Enum("coding", "design", "product", "marketing", "data", "writing",
                    name="challenge_domain", create_type=False),
            nullable=False,
        ),
        sa.Column("task_id", UUID(as_uuid=True),
                  sa.ForeignKey("challenge_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column(
            "status",
            sa.Enum("pending", "active", "completed", "cancelled", "expired",
                    name="match_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("winner_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("challenger_elo_before", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("opponent_elo_before", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("challenger_elo_after", sa.Integer, nullable=True),
        sa.Column("opponent_elo_after", sa.Integer, nullable=True),
        sa.Column("invite_message", sa.String(200), nullable=True),
        sa.Column("spectator_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        # duration must be 30 or 60 per PRD
        sa.CheckConstraint("duration_minutes IN (30, 60)", name="ck_matches_duration"),
    )
    op.create_index("ix_matches_challenger_id", "matches", ["challenger_id"])
    op.create_index("ix_matches_opponent_id", "matches", ["opponent_id"])
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_created_at", "matches", ["created_at"])

    # ── challenge_submissions ─────────────────────────────────────────────────
    op.create_table(
        "challenge_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("match_id", UUID(as_uuid=True),
                  sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("language", sa.String(40), nullable=True),
        sa.Column("submitted_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("score_breakdown", JSONB, nullable=True),
        sa.Column("ai_feedback", sa.Text, nullable=True),
        sa.Column("is_auto", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
        sa.UniqueConstraint("match_id", "user_id",
                            name="uq_challenge_submission_match_user"),
    )
    op.create_index("ix_challenge_submissions_match_id",
                    "challenge_submissions", ["match_id"])
    op.create_index("ix_challenge_submissions_user_id",
                    "challenge_submissions", ["user_id"])

    # ── user_elo ──────────────────────────────────────────────────────────────
    op.create_table(
        "user_elo",
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("elo", sa.Integer, nullable=False, server_default="1000"),
        sa.Column(
            "tier",
            sa.Enum("bronze", "silver", "gold", "platinum", "diamond", "elite",
                    name="elo_tier", create_type=False),
            nullable=False,
            server_default="silver",
        ),
        sa.Column("matches_played", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer, nullable=False, server_default="0"),
        sa.Column("peak_elo", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("current_streak", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("NOW()")),
    )

    # ── Seed challenge tasks (10 tasks across all 6 domains) ──────────────────
    op.execute(sa.text("""
        INSERT INTO challenge_tasks
            (id, domain, title, description, requirements, is_active, created_at)
        VALUES
        (gen_random_uuid(), 'coding', 'Two Sum',
         'Given an array of integers and a target, return indices of the two numbers that add up to target.',
         'Each input has exactly one solution. You may not use the same element twice.',
         true, NOW()),
        (gen_random_uuid(), 'coding', 'Reverse a Linked List',
         'Given the head of a singly linked list, reverse the list and return the reversed list.',
         'Implement an iterative solution. Time complexity must be O(n).',
         true, NOW()),
        (gen_random_uuid(), 'coding', 'Valid Parentheses',
         'Given a string containing only brackets, determine if the input string is valid.',
         'Open brackets must be closed by the same type and in the correct order.',
         true, NOW()),
        (gen_random_uuid(), 'design', 'Mobile Onboarding Flow',
         'Design a 3-screen onboarding flow for a fintech mobile app targeting first-time investors.',
         'Include: welcome screen, value proposition, and account setup. Focus on clarity and trust.',
         true, NOW()),
        (gen_random_uuid(), 'design', 'E-commerce Product Page Redesign',
         'Redesign the product detail page for a fashion e-commerce app to improve conversion.',
         'Include: image gallery, size selector, reviews, and add-to-cart CTA. Mobile-first.',
         true, NOW()),
        (gen_random_uuid(), 'product', 'Improve Retention for a Streaming App',
         'A streaming app has 40% D7 retention. Propose a product strategy to improve it to 60% in 3 months.',
         'Include: problem diagnosis, proposed features, success metrics, and tradeoffs.',
         true, NOW()),
        (gen_random_uuid(), 'product', 'Design a Notification System',
         'Design the notification system for a social media platform with 10M daily active users.',
         'Cover: notification types, delivery channels, user preferences, and technical architecture.',
         true, NOW()),
        (gen_random_uuid(), 'marketing', 'Launch Campaign for a B2B SaaS Tool',
         'Create a go-to-market campaign for a new project management SaaS targeting SMBs.',
         'Include: target audience, key messages, channels, and a 30-day launch plan.',
         true, NOW()),
        (gen_random_uuid(), 'data', 'Sales Funnel Analysis',
         'Given a dataset of user events (signup, trial_start, upgrade, churn), calculate conversion rates.',
         'Write SQL queries to compute: signup-to-trial rate, trial-to-paid rate, and monthly churn rate.',
         true, NOW()),
        (gen_random_uuid(), 'data', 'Cohort Retention Analysis',
         'Write a SQL query to compute weekly cohort retention for users who signed up in the last 8 weeks.',
         'Output: cohort_week, week_number, users_retained, retention_rate.',
         true, NOW()),
        (gen_random_uuid(), 'writing', 'Product Announcement Blog Post',
         'Write a 300-400 word blog post announcing a new AI-powered feature for a productivity app.',
         'Tone: professional but approachable. Include: headline, problem, feature description, and CTA.',
         true, NOW())
        ON CONFLICT DO NOTHING;
    """))


def downgrade() -> None:
    op.drop_index("ix_challenge_submissions_user_id", "challenge_submissions")
    op.drop_index("ix_challenge_submissions_match_id", "challenge_submissions")
    op.drop_index("ix_matches_created_at", "matches")
    op.drop_index("ix_matches_status", "matches")
    op.drop_index("ix_matches_opponent_id", "matches")
    op.drop_index("ix_matches_challenger_id", "matches")
    op.drop_index("ix_challenge_tasks_domain", "challenge_tasks")
    op.drop_table("user_elo")
    op.drop_table("challenge_submissions")
    op.drop_table("matches")
    op.drop_table("challenge_tasks")
    op.execute("DROP TYPE IF EXISTS elo_tier")
    op.execute("DROP TYPE IF EXISTS match_status")
    op.execute("DROP TYPE IF EXISTS challenge_domain")
