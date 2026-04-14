"""Part 3: Global Leaderboards + Ranking Tiers

Revision ID: 012_part3_leaderboards
Revises: 011
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '012_part3_leaderboards'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to user_elo table
    op.add_column('user_elo', sa.Column('coding_elo', sa.Integer(), nullable=False, server_default='1000'))
    op.add_column('user_elo', sa.Column('weekly_elo_gain', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user_elo', sa.Column('monthly_elo_gain', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user_elo', sa.Column('global_rank', sa.Integer(), nullable=True))
    op.add_column('user_elo', sa.Column('country_rank', sa.Integer(), nullable=True))
    op.add_column('user_elo', sa.Column('placement_matches_done', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user_elo', sa.Column('is_placement_complete', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('user_elo', sa.Column('season_id', sa.Integer(), nullable=True))
    
    # Add country and experience_level to users table if not exists
    op.add_column('users', sa.Column('country', sa.String(2), nullable=True))
    op.add_column('users', sa.Column('experience_level', sa.String(20), nullable=True))
    
    # Create seasons table
    op.create_table(
        'seasons',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('season_number', sa.Integer(), unique=True, nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('reset_factor', sa.Numeric(3, 2), nullable=False, server_default='0.20'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_seasons_status', 'seasons', ['status'])
    
    # Create elo_events table
    op.create_table(
        'elo_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('elo_before', sa.Integer(), nullable=False),
        sa.Column('elo_change', sa.Integer(), nullable=False),
        sa.Column('elo_after', sa.Integer(), nullable=False),
        sa.Column('tier_before', sa.String(20), nullable=False),
        sa.Column('tier_after', sa.String(20), nullable=True),
        sa.Column('opponent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('matches.id'), nullable=True),
        sa.Column('challenge_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_elo_events_user_date', 'elo_events', ['user_id', 'created_at'])
    op.create_index('idx_elo_events_season', 'elo_events', ['season_id'])
    
    # Create tier_history table
    op.create_table(
        'tier_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('tier_from', sa.String(20), nullable=False),
        sa.Column('tier_to', sa.String(20), nullable=False),
        sa.Column('elo_at_change', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_tier_history_user', 'tier_history', ['user_id', 'changed_at'])
    
    # Create season_results table
    op.create_table(
        'season_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('final_elo', sa.Integer(), nullable=False),
        sa.Column('final_tier', sa.String(20), nullable=False),
        sa.Column('global_rank', sa.Integer(), nullable=True),
        sa.Column('country_rank', sa.Integer(), nullable=True),
        sa.Column('elo_gained', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_season_results_season', 'season_results', ['season_id', 'global_rank'])
    
    # Create leaderboard_cache_meta table
    op.create_table(
        'leaderboard_cache_meta',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('board_type', sa.String(30), unique=True, nullable=False),
        sa.Column('last_computed', sa.DateTime(), nullable=False),
        sa.Column('total_entries', sa.Integer(), nullable=False, server_default='0'),
    )
    
    # Create indexes for leaderboard performance
    op.create_index('idx_user_elo_elo_desc', 'user_elo', [sa.text('elo DESC')])
    op.create_index('idx_user_elo_coding_desc', 'user_elo', [sa.text('coding_elo DESC')])
    op.create_index('idx_user_elo_weekly_desc', 'user_elo', [sa.text('weekly_elo_gain DESC')])
    op.create_index('idx_user_elo_monthly_desc', 'user_elo', [sa.text('monthly_elo_gain DESC')])
    op.create_index('idx_users_country', 'users', ['country'])
    op.create_index('idx_users_experience_level', 'users', ['experience_level'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_users_experience_level', 'users')
    op.drop_index('idx_users_country', 'users')
    op.drop_index('idx_user_elo_monthly_desc', 'user_elo')
    op.drop_index('idx_user_elo_weekly_desc', 'user_elo')
    op.drop_index('idx_user_elo_coding_desc', 'user_elo')
    op.drop_index('idx_user_elo_elo_desc', 'user_elo')
    
    # Drop tables
    op.drop_table('leaderboard_cache_meta')
    op.drop_table('season_results')
    op.drop_table('tier_history')
    op.drop_table('elo_events')
    op.drop_table('seasons')
    
    # Drop columns from users
    op.drop_column('users', 'experience_level')
    op.drop_column('users', 'country')
    
    # Drop columns from user_elo
    op.drop_column('user_elo', 'season_id')
    op.drop_column('user_elo', 'is_placement_complete')
    op.drop_column('user_elo', 'placement_matches_done')
    op.drop_column('user_elo', 'country_rank')
    op.drop_column('user_elo', 'global_rank')
    op.drop_column('user_elo', 'monthly_elo_gain')
    op.drop_column('user_elo', 'weekly_elo_gain')
    op.drop_column('user_elo', 'coding_elo')
