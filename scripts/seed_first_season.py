"""Seed the first season."""

import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.leaderboard import Season


async def seed_first_season():
    """Create the first season."""
    print("🌱 Seeding first season...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Check if season already exists
            result = await db.execute(
                select(Season).where(Season.season_number == 1)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print("⚠️  Season 1 already exists, skipping...")
                return
            
            # Create first season (90 days from today)
            season = Season(
                season_number=1,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=90),
                status='active',
                reset_factor=0.20
            )
            db.add(season)
            await db.commit()
            
            print(f"✅ Season 1 created successfully!")
            print(f"   Start: {season.start_date}")
            print(f"   End: {season.end_date}")
            print(f"   Duration: 90 days")
            
        except Exception as e:
            print(f"❌ Error seeding season: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed_first_season())
