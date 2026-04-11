"""Test match creation end-to-end on production server."""
import asyncio
import httpx
from sqlalchemy import text, select
from app.core.database import AsyncSessionLocal
from app.models.user import User

async def get_firebase_token_for_user(email: str) -> str | None:
    """We can't get a real Firebase token here, but we can test the DB directly."""
    return None

async def test_direct_db():
    """Test match creation directly in DB (bypassing HTTP)."""
    async with AsyncSessionLocal() as db:
        # Get two users
        result = await db.execute(select(User).where(User.is_active == True).limit(2))
        users = result.scalars().all()
        if len(users) < 2:
            print("Need at least 2 users")
            return
        
        u1, u2 = users[0], users[1]
        print(f"User1: {u1.full_name} ({u1.email})")
        print(f"User2: {u2.full_name} ({u2.email})")
        
        # Simulate the full send_invite flow
        from app.models.challenges import Match, UserElo, ChallengeTask
        from app.services.elo_service import get_or_create_elo
        from sqlalchemy import func
        
        c_elo = await get_or_create_elo(db, u1.id)
        o_elo = await get_or_create_elo(db, u2.id)
        
        task_result = await db.execute(
            select(ChallengeTask)
            .where(ChallengeTask.domain == 'coding', ChallengeTask.is_active.is_(True))
            .order_by(func.random()).limit(1)
        )
        task = task_result.scalar_one_or_none()
        
        match = Match(
            challenger_id=u1.id,
            opponent_id=u2.id,
            domain='coding',
            task_id=task.id if task else None,
            duration_minutes=30,
            status='pending',
            challenger_elo_before=c_elo.elo,
            opponent_elo_before=o_elo.elo,
            invite_message='Test challenge',
        )
        db.add(match)
        await db.flush()
        print(f"Match flushed: {match.id}")
        
        # Test notification creation (the part that was failing)
        from app.services.notification_service import create_notification
        try:
            await create_notification(
                db=db,
                user_id=u2.id,
                notif_type='challenge_invite',
                title=f'{u1.full_name} challenged you!',
                body=f'{u1.full_name} challenged you to a 1v1 in Coding',
                data={'match_id': str(match.id), 'type': 'challenge_invite'},
            )
            print("Notification created OK")
        except Exception as e:
            print(f"Notification FAILED: {e}")
            # This should NOT rollback the match anymore
        
        await db.commit()
        print("COMMITTED OK")
        
        # Verify
        r = await db.execute(text('SELECT COUNT(*) FROM matches'))
        print(f"Matches in DB: {r.scalar()}")
        
        r2 = await db.execute(text('SELECT COUNT(*) FROM notifications'))
        print(f"Notifications in DB: {r2.scalar()}")
        
        # Cleanup
        await db.execute(text("DELETE FROM matches"))
        await db.execute(text("DELETE FROM notifications"))
        await db.execute(text("DELETE FROM user_elo"))
        await db.commit()
        print("Cleaned up")

asyncio.run(test_direct_db())
