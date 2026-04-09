"""Initial schema — users, candidate_profiles, recruiter_profiles.

Revision ID: 001
Revises: 
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_role enum only if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                CREATE TYPE user_role AS ENUM ('candidate', 'recruiter');
            END IF;
        END
        $$
    """)

    # Create users table only if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            firebase_uid VARCHAR(128) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            full_name VARCHAR(120) NOT NULL,
            phone VARCHAR(20),
            role user_role,
            avatar_url TEXT,
            onboarding_complete BOOLEAN NOT NULL DEFAULT false,
            is_verified BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_firebase_uid ON users (firebase_uid)")

    # Create candidate_profiles table only if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS candidate_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID UNIQUE NOT NULL REFERENCES users(id),
            headline VARCHAR(120),
            bio TEXT,
            city VARCHAR(100),
            github_url TEXT,
            linkedin_url TEXT,
            portfolio_url TEXT,
            skill_tags VARCHAR[] NOT NULL DEFAULT '{}',
            career_goal VARCHAR(60),
            skill_score INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)

    # Create recruiter_profiles table only if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS recruiter_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID UNIQUE NOT NULL REFERENCES users(id),
            company_name VARCHAR(120),
            company_size VARCHAR(20),
            role_at_company VARCHAR(100),
            hiring_domains VARCHAR[] NOT NULL DEFAULT '{}',
            company_website TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recruiter_profiles")
    op.execute("DROP TABLE IF EXISTS candidate_profiles")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS user_role")
