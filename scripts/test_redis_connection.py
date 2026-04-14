"""Test Redis connection and basic operations."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from app.services.redis_service import RedisService


async def test_redis():
    """Test Redis connection and operations."""
    print("🔍 Testing Redis connection...")
    
    redis = RedisService()
    
    try:
        # Test 1: Basic ping
        print("\n1️⃣ Testing basic connection...")
        await redis.set("test_key", "test_value")
        value = await redis.get("test_key")
        if value == "test_value":
            print("   ✅ Basic read/write works!")
        else:
            print("   ❌ Basic read/write failed!")
            return False
        
        # Test 2: Sorted set operations (used for leaderboards)
        print("\n2️⃣ Testing sorted set operations...")
        await redis.zadd("test_leaderboard", {"user1": 1500, "user2": 1200, "user3": 1800})
        
        # Get rank
        rank = await redis.zrevrank("test_leaderboard", "user3")
        if rank == 0:  # user3 has highest score, so rank 0
            print("   ✅ Sorted set rank lookup works!")
        else:
            print(f"   ❌ Sorted set rank lookup failed! Got rank: {rank}")
            return False
        
        # Get range
        top_users = await redis.zrevrange("test_leaderboard", 0, 2, withscores=True)
        if len(top_users) == 6:  # 3 users * 2 (user_id + score)
            print("   ✅ Sorted set range query works!")
        else:
            print(f"   ❌ Sorted set range query failed! Got: {top_users}")
            return False
        
        # Test 3: Expiration
        print("\n3️⃣ Testing key expiration...")
        await redis.setex("temp_key", 1, "temp_value")
        value = await redis.get("temp_key")
        if value == "temp_value":
            print("   ✅ Key expiration set works!")
        else:
            print("   ❌ Key expiration failed!")
            return False
        
        # Test 4: Delete
        print("\n4️⃣ Testing delete operations...")
        await redis.delete("test_key", "test_leaderboard", "temp_key")
        value = await redis.get("test_key")
        if value is None:
            print("   ✅ Delete works!")
        else:
            print("   ❌ Delete failed!")
            return False
        
        print("\n" + "="*50)
        print("🎉 All Redis tests passed!")
        print("="*50)
        print("\n✅ Redis is ready for HireX leaderboards!")
        return True
        
    except Exception as e:
        print(f"\n❌ Redis test failed with error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Redis is installed and running")
        print("2. Check REDIS_URL in .env file")
        print("3. Try: redis-cli ping (should return PONG)")
        print("4. See REDIS_INSTALLATION_GUIDE.md for help")
        return False
    finally:
        await redis.close()


if __name__ == "__main__":
    result = asyncio.run(test_redis())
    sys.exit(0 if result else 1)
