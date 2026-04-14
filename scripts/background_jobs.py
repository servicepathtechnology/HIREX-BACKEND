"""Background jobs for leaderboard maintenance.

This script can be run as a cron job or scheduled task.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.challenges import UserElo
from app.models.user import User
from app.models.leaderboard import Season, SeasonResult
from app.services.redis_service import RedisService


async def refresh_rank_cache():
    """Refresh global and country ranks in database.
    
    Run this every 5 minutes.
    """
    print("🔄 Refreshing rank cache...")
    
    redis = RedisService()
    db = AsyncSessionLocal()
    
    try:
        # Get all users with ELO
        result = await db.execute(
            select(UserElo, User)
            .join(User, UserElo.user_id == User.id)
        )
        rows = result.all()
        
        updates = []
        for user_elo, user in rows:
            user_id_str = str(user.id)
            
            # Get global rank
            global_rank = await redis.zrevrank("lb:global", user_id_str)
            if global_rank is not None:
                global_rank += 1  # Convert to 1-indexed
            
            # Get country rank
            country_rank = None
            if user.country:
                country_rank = await redis.zrevrank(
                    f"lb:country:{user.country}",
                    user_id_str
                )
                if country_rank is not None:
                    country_rank += 1
            
            # Update if changed
            if (user_elo.global_rank != global_rank or 
                user_elo.country_rank != country_rank):
                updates.append({
                    'user_id': user.id,
                    'global_rank': global_rank,
                    'country_rank': country_rank,
                })
        
        # Batch update
        if updates:
            for update_data in updates:
                await db.execute(
                    update(UserElo)
                    .where(UserElo.user_id == update_data['user_id'])
                    .values(
                        global_rank=update_data['global_rank'],
                        country_rank=update_data['country_rank'],
                    )
                )
            await db.commit()
            print(f"   ✅ Updated {len(updates)} user ranks")
        else:
            print("   ℹ️  No rank changes")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        await db.rollback()
    finally:
        await db.close()
        await redis.close()


async def weekly_leaderboard_reset():
    """Reset weekly leaderboard.
    
    Run this every Monday at 00:01 UTC.
    """
    print("📅 Resetting weekly leaderboard...")
    
    redis = RedisService()
    db = AsyncSessionLocal()
    
    try:
        # Get top 3 from weekly leaderboard
        top_3 = await redis.zrevrange("lb:weekly", 0, 2, withscores=True)
        
        if top_3:
            print(f"   🏆 Weekly winners:")
            for i in range(0, len(top_3), 2):
                user_id = top_3[i]
                elo_gain = int(top_3[i + 1])
                rank = (i // 2) + 1
                print(f"      #{rank}: User {user_id} (+{elo_gain} ELO)")
                
                # TODO: Award badges and send notifications
                # await award_weekly_winner_badge(user_id, rank)
                # await send_weekly_winner_notification(user_id, rank)
        
        # Reset weekly_elo_gain for all users
        await db.execute(
            update(UserElo).values(weekly_elo_gain=0)
        )
        await db.commit()
        
        # Clear Redis weekly leaderboard
        await redis.delete("lb:weekly")
        
        # Rebuild from scratch (all zeros)
        result = await db.execute(select(UserElo))
        users = result.scalars().all()
        
        weekly_data = {str(u.user_id): 0 for u in users}
        if weekly_data:
            await redis.zadd("lb:weekly", weekly_data)
        
        print(f"   ✅ Weekly leaderboard reset complete")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        await db.rollback()
    finally:
        await db.close()
        await redis.close()


async def monthly_leaderboard_reset():
    """Reset monthly leaderboard.
    
    Run this on the 1st of each month at 00:01 UTC.
    """
    print("📅 Resetting monthly leaderboard...")
    
    redis = RedisService()
    db = AsyncSessionLocal()
    
    try:
        # Get top 3 from monthly leaderboard
        top_3 = await redis.zrevrange("lb:monthly", 0, 2, withscores=True)
        
        if top_3:
            print(f"   🏆 Monthly champions:")
            for i in range(0, len(top_3), 2):
                user_id = top_3[i]
                elo_gain = int(top_3[i + 1])
                rank = (i // 2) + 1
                print(f"      #{rank}: User {user_id} (+{elo_gain} ELO)")
                
                # TODO: Award badges and send notifications
                # await award_monthly_champion_badge(user_id, rank)
                # await send_monthly_champion_notification(user_id, rank)
        
        # Reset monthly_elo_gain for all users
        await db.execute(
            update(UserElo).values(monthly_elo_gain=0)
        )
        await db.commit()
        
        # Clear Redis monthly leaderboard
        await redis.delete("lb:monthly")
        
        # Rebuild from scratch (all zeros)
        result = await db.execute(select(UserElo))
        users = result.scalars().all()
        
        monthly_data = {str(u.user_id): 0 for u in users}
        if monthly_data:
            await redis.zadd("lb:monthly", monthly_data)
        
        print(f"   ✅ Monthly leaderboard reset complete")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        await db.rollback()
    finally:
        await db.close()
        await redis.close()


async def season_end():
    """End current season and start new one.
    
    Run this manually or when season end_date is reached.
    """
    print("🏁 Ending current season...")
    
    db = AsyncSessionLocal()
    
    try:
        # Get active season
        result = await db.execute(
            select(Season).where(Season.status == "active")
        )
        season = result.scalar_one_or_none()
        
        if not season:
            print("   ⚠️  No active season found")
            return
        
        print(f"   Ending Season {season.season_number}")
        
        # Snapshot all user standings
        result = await db.execute(
            select(UserElo, User)
            .join(User, UserElo.user_id == User.id)
        )
        rows = result.all()
        
        for user_elo, user in rows:
            season_result = SeasonResult(
                season_id=season.id,
                user_id=user.id,
                final_elo=user_elo.elo,
                final_tier=user_elo.tier,
                global_rank=user_elo.global_rank,
                country_rank=user_elo.country_rank,
                elo_gained=user_elo.weekly_elo_gain + user_elo.monthly_elo_gain,
            )
            db.add(season_result)
        
        # Apply soft reset (20% toward 1000)
        reset_factor = float(season.reset_factor)
        await db.execute(
            update(UserElo).values(
                elo=UserElo.elo - ((UserElo.elo - 1000) * reset_factor)
            )
        )
        
        # Mark season as ended
        season.status = "ended"
        
        # Create new season
        new_season = Season(
            season_number=season.season_number + 1,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            status="active",
            reset_factor=0.20,
        )
        db.add(new_season)
        
        await db.commit()
        
        print(f"   ✅ Season {season.season_number} ended")
        print(f"   ✅ Season {new_season.season_number} started")
        print(f"   📊 {len(rows)} user standings saved")
        
        # TODO: Send season end notifications to all users
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        await db.rollback()
    finally:
        await db.close()


async def main():
    """Run background jobs based on command line argument."""
    if len(sys.argv) < 2:
        print("Usage: python background_jobs.py <job_name>")
        print("\nAvailable jobs:")
        print("  refresh_ranks    - Refresh rank cache (run every 5 min)")
        print("  weekly_reset     - Reset weekly leaderboard (run Monday 00:01 UTC)")
        print("  monthly_reset    - Reset monthly leaderboard (run 1st of month)")
        print("  season_end       - End season and start new one (manual)")
        sys.exit(1)
    
    job = sys.argv[1]
    
    if job == "refresh_ranks":
        await refresh_rank_cache()
    elif job == "weekly_reset":
        await weekly_leaderboard_reset()
    elif job == "monthly_reset":
        await monthly_leaderboard_reset()
    elif job == "season_end":
        await season_end()
    else:
        print(f"❌ Unknown job: {job}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
