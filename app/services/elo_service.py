"""ELO Service — Complete implementation for Part 3."""

import math
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.challenges import UserElo
from app.models.leaderboard import EloEvent, TierHistory, Season
from app.models.user import User
from app.services.redis_service import RedisService
from app.services.notification_service import NotificationService


# Starting ELO for new users
STARTING_ELO = 1000


# K-factors by tier — higher K = more volatile ELO changes
K_FACTORS = {
    "bronze": 32,
    "silver": 28,
    "gold": 24,
    "platinum": 20,
    "diamond": 16,
    "elite": 12,
}

# Tier thresholds
TIER_THRESHOLDS = [
    (1800, "elite"),
    (1600, "diamond"),
    (1400, "platinum"),
    (1200, "gold"),
    (1000, "silver"),
    (0, "bronze"),
]


class EloService:
    """Handles all ELO calculations, updates, and leaderboard management."""

    def __init__(self, db: AsyncSession, redis: RedisService, notif: NotificationService):
        self.db = db
        self.redis = redis
        self.notif = notif

    @staticmethod
    def get_tier_from_elo(elo: int) -> str:
        """Map ELO score to tier name."""
        for threshold, tier in TIER_THRESHOLDS:
            if elo >= threshold:
                return tier
        return "bronze"

    @staticmethod
    def get_k_factor(tier: str, is_placement_complete: bool) -> int:
        """Get K-factor for ELO calculation."""
        if not is_placement_complete:
            return 64  # Doubled K for placement matches
        return K_FACTORS.get(tier, 32)

    @staticmethod
    def expected_score(my_elo: int, opponent_elo: int) -> float:
        """Calculate expected win probability."""
        return 1 / (1 + math.pow(10, (opponent_elo - my_elo) / 400))

    @staticmethod
    def calculate_elo_change(
        my_elo: int,
        opponent_elo: int,
        result: float,
        k_factor: int
    ) -> int:
        """Calculate ELO change based on match result.
        
        Args:
            my_elo: Current ELO
            opponent_elo: Opponent's ELO
            result: 1.0 = win, 0.5 = draw, 0.0 = loss
            k_factor: K-factor for this tier
        """
        expected = EloService.expected_score(my_elo, opponent_elo)
        change = round(k_factor * (result - expected))
        return change

    async def get_current_season(self) -> Optional[Season]:
        """Get the active season."""
        result = await self.db.execute(
            select(Season).where(Season.status == "active").order_by(Season.id.desc())
        )
        return result.scalar_one_or_none()

    async def process_elo_update(
        self,
        user_id: uuid.UUID,
        event_type: str,
        opponent_id: Optional[uuid.UUID] = None,
        match_id: Optional[uuid.UUID] = None,
        challenge_id: Optional[uuid.UUID] = None,
        result: Optional[float] = None,
        flat_elo_change: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process an ELO update event.
        
        Args:
            user_id: User whose ELO is changing
            event_type: Type of event (1v1_win, daily_complete, etc.)
            opponent_id: Opponent for 1v1 events
            match_id: Match ID for 1v1 events
            challenge_id: Challenge ID for challenge events
            result: 1.0/0.5/0.0 for win/draw/loss
            flat_elo_change: Fixed ELO change for non-1v1 events
        """
        # Get user ELO record
        user_elo_result = await self.db.execute(
            select(UserElo).where(UserElo.user_id == user_id)
        )
        user_elo = user_elo_result.scalar_one_or_none()
        
        if not user_elo:
            # Create new ELO record
            user_elo = UserElo(
                user_id=user_id,
                elo=1000,
                tier="silver",
                coding_elo=1000,
            )
            self.db.add(user_elo)
            await self.db.flush()

        # Get current season
        season = await self.get_current_season()
        season_id = season.id if season else None

        # Calculate ELO change
        if flat_elo_change is not None:
            change = flat_elo_change
        else:
            # 1v1 match — calculate based on opponent ELO
            opponent_elo_result = await self.db.execute(
                select(UserElo).where(UserElo.user_id == opponent_id)
            )
            opponent_elo = opponent_elo_result.scalar_one_or_none()
            opponent_elo_value = opponent_elo.elo if opponent_elo else 1000
            
            k_factor = self.get_k_factor(user_elo.tier, user_elo.is_placement_complete)
            change = self.calculate_elo_change(
                user_elo.elo,
                opponent_elo_value,
                result,
                k_factor
            )

        # Calculate new ELO and tier
        elo_before = user_elo.elo
        elo_after = elo_before + change
        tier_before = user_elo.tier
        tier_after = self.get_tier_from_elo(elo_after)
        tier_changed = tier_after != tier_before

        # Update user_elo record
        user_elo.elo = elo_after
        user_elo.tier = tier_after
        user_elo.weekly_elo_gain += change
        user_elo.monthly_elo_gain += change
        user_elo.peak_elo = max(user_elo.peak_elo, elo_after)
        
        # Update coding_elo if coding event
        if event_type in ["1v1_win", "1v1_loss", "1v1_draw", "daily_complete", "weekly_complete"]:
            user_elo.coding_elo += change
        
        # Update match stats for 1v1 events
        if event_type in ["1v1_win", "1v1_loss", "1v1_draw"]:
            user_elo.matches_played += 1
            if event_type == "1v1_win":
                user_elo.wins += 1
                user_elo.current_streak += 1
            elif event_type == "1v1_loss":
                user_elo.losses += 1
                user_elo.current_streak = 0
            else:
                user_elo.draws += 1
        
        # Update placement matches
        if not user_elo.is_placement_complete and event_type in ["1v1_win", "1v1_loss", "1v1_draw"]:
            user_elo.placement_matches_done += 1
            if user_elo.placement_matches_done >= 10:
                user_elo.is_placement_complete = True

        # Create ELO event record
        elo_event = EloEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            event_type=event_type,
            elo_before=elo_before,
            elo_change=change,
            elo_after=elo_after,
            tier_before=tier_before,
            tier_after=tier_after if tier_changed else None,
            opponent_id=opponent_id,
            match_id=match_id,
            challenge_id=challenge_id,
            season_id=season_id,
        )
        self.db.add(elo_event)

        # Create tier history if tier changed
        if tier_changed:
            tier_history = TierHistory(
                id=uuid.uuid4(),
                user_id=user_id,
                tier_from=tier_before,
                tier_to=tier_after,
                elo_at_change=elo_after,
                direction="promotion" if change > 0 else "demotion",
                season_id=season_id,
            )
            self.db.add(tier_history)

        await self.db.commit()

        # Update Redis sorted sets
        await self.update_leaderboard_sorted_sets(user_id, elo_after, user_elo)

        # Send notifications if tier changed
        if tier_changed:
            await self.send_tier_change_notification(
                user_id, tier_before, tier_after, elo_after
            )

        return {
            "elo_after": elo_after,
            "change": change,
            "tier_after": tier_after,
            "tier_changed": tier_changed,
        }

    async def update_leaderboard_sorted_sets(
        self,
        user_id: uuid.UUID,
        new_elo: int,
        user_elo: UserElo
    ):
        """Update Redis sorted sets for all leaderboard types."""
        user_id_str = str(user_id)
        
        # Get user country and experience level
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Global leaderboard
        await self.redis.zadd("lb:global", {user_id_str: new_elo})
        
        # Country leaderboard
        if user and user.country:
            await self.redis.zadd(f"lb:country:{user.country}", {user_id_str: new_elo})
        
        # Domain leaderboard (coding)
        await self.redis.zadd("lb:domain:coding", {user_id_str: user_elo.coding_elo})
        
        # Experience level leaderboard
        if user and user.experience_level:
            await self.redis.zadd(
                f"lb:exp:{user.experience_level}",
                {user_id_str: new_elo}
            )
        
        # Weekly leaderboard
        await self.redis.zadd("lb:weekly", {user_id_str: user_elo.weekly_elo_gain})
        
        # Monthly leaderboard
        await self.redis.zadd("lb:monthly", {user_id_str: user_elo.monthly_elo_gain})
        
        # Invalidate user rank cache
        await self.redis.delete(f"user:rank:global:{user_id_str}")
        await self.redis.delete(f"user:rank:country:{user_id_str}")
        await self.redis.delete(f"user:elo:{user_id_str}")

    async def get_global_rank(self, user_id: uuid.UUID) -> int:
        """Get user's global rank from Redis sorted set."""
        user_id_str = str(user_id)
        
        # Check cache
        cached = await self.redis.get(f"user:rank:global:{user_id_str}")
        if cached:
            return int(cached)
        
        # Get from sorted set
        rank = await self.redis.zrevrank("lb:global", user_id_str)
        if rank is not None:
            rank += 1  # Convert 0-indexed to 1-indexed
            await self.redis.setex(f"user:rank:global:{user_id_str}", 60, str(rank))
            return rank
        
        return -1

    async def send_tier_change_notification(
        self,
        user_id: uuid.UUID,
        tier_from: str,
        tier_to: str,
        elo: int
    ):
        """Send FCM notification for tier change."""
        direction = "promotion" if TIER_THRESHOLDS[0][0] > TIER_THRESHOLDS[1][0] else "promotion"
        
        if tier_to > tier_from:  # Promotion
            title = f"Tier Up! You are now {tier_to.upper()}!"
            body = f"Congratulations! Your ELO hit {elo}. Welcome to {tier_to.capitalize()}!"
        else:  # Demotion
            title = "Your tier changed"
            body = f"Your ELO dropped to {elo}. You are now {tier_to.capitalize()}. Keep going!"
        
        await self.notif.send_push_notification(
            user_id=user_id,
            title=title,
            body=body,
            data={"screen": "tier_detail", "tier": tier_to, "elo": str(elo)}
        )



# ── Standalone helper functions ──────────────────────────────────────────────

async def get_or_create_elo(db: AsyncSession, user_id: uuid.UUID) -> UserElo:
    """Get or create UserElo record for a user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        UserElo record
    """
    result = await db.execute(
        select(UserElo).where(UserElo.user_id == user_id)
    )
    user_elo = result.scalar_one_or_none()
    
    if not user_elo:
        # Create new ELO record with starting values
        user_elo = UserElo(
            user_id=user_id,
            elo=STARTING_ELO,
            tier="silver",
            coding_elo=STARTING_ELO,
            matches_played=0,
            wins=0,
            losses=0,
            draws=0,
            peak_elo=STARTING_ELO,
            current_streak=0,
            weekly_elo_gain=0,
            monthly_elo_gain=0,
            placement_matches_done=0,
            is_placement_complete=False,
        )
        db.add(user_elo)
        await db.flush()
    
    return user_elo


def _tier_from_elo(elo: int) -> str:
    """Map ELO score to tier name.
    
    Args:
        elo: ELO score
        
    Returns:
        Tier name (bronze, silver, gold, platinum, diamond, elite)
    """
    for threshold, tier in TIER_THRESHOLDS:
        if elo >= threshold:
            return tier
    return "bronze"
