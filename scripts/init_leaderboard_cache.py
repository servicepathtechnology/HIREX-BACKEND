"""Initialize Redis leaderboard sorted sets from existing ELO data."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.challenges import UserElo
from app.models.user import User
from app.services.redis_service import RedisService


async def init_leaderboard_cache():
    """Initialize all Redis sorted sets from database."""
    print("🚀 Initializing leaderboard cache...")
    
    redis = RedisService()
    db = AsyncSessionLocal()
    
    try:
        # Fetch all user ELO records with user data
        result = await db.execute(
            select(UserElo, User)
            .join(User, UserElo.user_id == User.id)
        )
        rows = result.all()
        
        print(f"📊 Found {len(rows)} users with ELO records")
        
        # Prepare data for sorted sets
        global_data = {}
        country_data = {}
        domain_data = {}
        exp_data = {}
        weekly_data = {}
        monthly_data = {}
        
        for user_elo, user in rows:
            user_id_str = str(user.id)
            
            # Global leaderboard
            global_data[user_id_str] = user_elo.elo
            
            # Country leaderboard
            if user.country:
                country_key = f"lb:country:{user.country}"
                if country_key not in country_data:
                    country_data[country_key] = {}
                country_data[country_key][user_id_str] = user_elo.elo
            
            # Domain leaderboard (coding)
            domain_data[user_id_str] = user_elo.coding_elo
            
            # Experience level leaderboard
            if user.experience_level:
                exp_key = f"lb:exp:{user.experience_level}"
                if exp_key not in exp_data:
                    exp_data[exp_key] = {}
                exp_data[exp_key][user_id_str] = user_elo.elo
            
            # Weekly leaderboard
            weekly_data[user_id_str] = user_elo.weekly_elo_gain
            
            # Monthly leaderboard
            monthly_data[user_id_str] = user_elo.monthly_elo_gain
        
        # Populate Redis sorted sets
        print("📝 Populating global leaderboard...")
        if global_data:
            await redis.zadd("lb:global", global_data)
        
        print("📝 Populating country leaderboards...")
        for country_key, data in country_data.items():
            if data:
                await redis.zadd(country_key, data)
        
        print("📝 Populating domain leaderboard...")
        if domain_data:
            await redis.zadd("lb:domain:coding", domain_data)
        
        print("📝 Populating experience leaderboards...")
        for exp_key, data in exp_data.items():
            if data:
                await redis.zadd(exp_key, data)
        
        print("📝 Populating weekly leaderboard...")
        if weekly_data:
            await redis.zadd("lb:weekly", weekly_data)
        
        print("📝 Populating monthly leaderboard...")
        if monthly_data:
            await redis.zadd("lb:monthly", monthly_data)
        
        print("✅ Leaderboard cache initialized successfully!")
        print(f"   - Global: {len(global_data)} users")
        print(f"   - Countries: {len(country_data)} leaderboards")
        print(f"   - Domain (coding): {len(domain_data)} users")
        print(f"   - Experience levels: {len(exp_data)} leaderboards")
        print(f"   - Weekly: {len(weekly_data)} users")
        print(f"   - Monthly: {len(monthly_data)} users")
        
    except Exception as e:
        print(f"❌ Error initializing cache: {e}")
        raise
    finally:
        await db.close()
        await redis.close()


if __name__ == "__main__":
    asyncio.run(init_leaderboard_cache())
