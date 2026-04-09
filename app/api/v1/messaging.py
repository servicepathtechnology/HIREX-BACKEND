"""Messaging API — Part 4."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.part4 import MessageThread, Message
from app.models.task import Task
from app.models.recruiter import PipelineEntry
from app.models.user import User, CandidateProfile

router = APIRouter(prefix="/messages", tags=["messaging"])
ws_router = APIRouter(tags=["websocket"])


class CreateThreadRequest(BaseModel):
    candidate_id: str
    task_id: str


class SendMessageRequest(BaseModel):
    content: str


async def _enrich_thread(thread: MessageThread, current_user_id: UUID, db: AsyncSession) -> dict:
    """Build thread dict with other party name/avatar and task title."""
    is_recruiter = thread.recruiter_id == current_user_id
    unread = thread.recruiter_unread_count if is_recruiter else thread.candidate_unread_count

    # Fetch other party info
    other_id = thread.candidate_id if is_recruiter else thread.recruiter_id
    other_result = await db.execute(select(User).where(User.id == other_id))
    other_user = other_result.scalar_one_or_none()

    # Fetch task title
    task_result = await db.execute(select(Task.title).where(Task.id == thread.task_id))
    task_title = task_result.scalar_one_or_none()

    return {
        "id": str(thread.id),
        "recruiter_id": str(thread.recruiter_id),
        "candidate_id": str(thread.candidate_id),
        "task_id": str(thread.task_id),
        "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else None,
        "last_message_preview": thread.last_message_preview,
        "unread_count": unread,
        "is_active": thread.is_active,
        "created_at": thread.created_at.isoformat(),
        "other_party_name": other_user.full_name if other_user else None,
        "other_party_avatar": other_user.avatar_url if other_user else None,
        "task_title": task_title,
    }


def _message_to_dict(msg: Message) -> dict:
    return {
        "id": str(msg.id),
        "thread_id": str(msg.thread_id),
        "sender_id": str(msg.sender_id),
        "content": msg.content,
        "is_read": msg.is_read,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat(),
    }


@router.post("/threads")
async def create_thread(
    payload: CreateThreadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can initiate threads.")

    candidate_id = UUID(payload.candidate_id)
    task_id = UUID(payload.task_id)

    pipeline_result = await db.execute(
        select(PipelineEntry).where(
            PipelineEntry.recruiter_id == current_user.id,
            PipelineEntry.candidate_id == candidate_id,
            PipelineEntry.task_id == task_id,
        )
    )
    if not pipeline_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Candidate must be shortlisted before messaging.")

    existing = await db.execute(
        select(MessageThread).where(
            MessageThread.recruiter_id == current_user.id,
            MessageThread.candidate_id == candidate_id,
            MessageThread.task_id == task_id,
        )
    )
    thread = existing.scalar_one_or_none()
    # Return existing thread enriched
    if thread:
        return await _enrich_thread(thread, current_user.id, db)

    thread = MessageThread(
        recruiter_id=current_user.id,
        candidate_id=candidate_id,
        task_id=task_id,
    )
    db.add(thread)
    await db.flush()
    await db.refresh(thread)
    return await _enrich_thread(thread, current_user.id, db)


@router.get("/threads")
async def list_threads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if current_user.role == "recruiter":
        query = select(MessageThread).where(
            MessageThread.recruiter_id == current_user.id,
            MessageThread.is_active == True,
        )
    else:
        query = select(MessageThread).where(
            MessageThread.candidate_id == current_user.id,
            MessageThread.is_active == True,
        )
    query = query.order_by(MessageThread.last_message_at.desc().nullslast())
    result = await db.execute(query)
    threads = result.scalars().all()
    enriched = []
    for t in threads:
        enriched.append(await _enrich_thread(t, current_user.id, db))
    return enriched


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    thread_result = await db.execute(select(MessageThread).where(MessageThread.id == thread_id))
    thread = thread_result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if thread.recruiter_id != current_user.id and thread.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.thread_id == thread_id)
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    msgs_result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    messages = msgs_result.scalars().all()

    return {
        "thread": await _enrich_thread(thread, current_user.id, db),
        "messages": [_message_to_dict(m) for m in reversed(messages)],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (offset + len(messages)) < total,
    }


@router.post("/threads/{thread_id}/send")
async def send_message(
    thread_id: UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not payload.content or len(payload.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")
    if len(payload.content) > 1000:
        raise HTTPException(status_code=400, detail="Message too long (max 1000 chars).")

    thread_result = await db.execute(select(MessageThread).where(MessageThread.id == thread_id))
    thread = thread_result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if thread.recruiter_id != current_user.id and thread.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    msg = Message(
        thread_id=thread_id,
        sender_id=current_user.id,
        content=payload.content.strip(),
    )
    db.add(msg)

    thread.last_message_at = datetime.utcnow()
    thread.last_message_preview = payload.content[:200]

    if current_user.id == thread.recruiter_id:
        thread.candidate_unread_count = (thread.candidate_unread_count or 0) + 1
        recipient_id = thread.candidate_id
    else:
        thread.recruiter_unread_count = (thread.recruiter_unread_count or 0) + 1
        recipient_id = thread.recruiter_id

    await db.flush()
    await db.refresh(msg)
    msg_dict = _message_to_dict(msg)

    # Real-time delivery
    try:
        from backend.messaging.websocket_handler import publish_message
        await publish_message(str(recipient_id), {"type": "message", "data": msg_dict})
    except Exception:
        pass

    # FCM push + in-app notification
    try:
        from backend.notifications.fcm_service import push_new_message
        await push_new_message(db, recipient_id, current_user.full_name, payload.content[:60], thread_id)
    except Exception:
        pass

    from app.services.notification_service import create_notification
    await create_notification(
        db=db, user_id=recipient_id, notif_type="new_message",
        title="New Message",
        body=f"{current_user.full_name}: {payload.content[:80]}",
        data={"thread_id": str(thread_id), "type": "new_message"},
    )

    return msg_dict


@router.put("/threads/{thread_id}/read")
async def mark_thread_read(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    thread_result = await db.execute(select(MessageThread).where(MessageThread.id == thread_id))
    thread = thread_result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if thread.recruiter_id != current_user.id and thread.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    msgs_result = await db.execute(
        select(Message).where(
            Message.thread_id == thread_id,
            Message.sender_id != current_user.id,
            Message.is_read == False,
        )
    )
    messages = msgs_result.scalars().all()
    now = datetime.utcnow()
    for msg in messages:
        msg.is_read = True
        msg.read_at = now

    if current_user.id == thread.recruiter_id:
        thread.recruiter_unread_count = 0
        other_id = thread.candidate_id
    else:
        thread.candidate_unread_count = 0
        other_id = thread.recruiter_id

    await db.flush()

    if messages:
        try:
            from backend.messaging.websocket_handler import publish_message
            await publish_message(str(other_id), {
                "type": "read",
                "data": {
                    "thread_id": str(thread_id),
                    "read_by": str(current_user.id),
                    "up_to_message_id": str(messages[-1].id),
                },
            })
        except Exception:
            pass

    return {"status": "ok", "marked_read": len(messages)}


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if current_user.role == "recruiter":
        result = await db.execute(
            select(func.sum(MessageThread.recruiter_unread_count)).where(
                MessageThread.recruiter_id == current_user.id,
                MessageThread.is_active == True,
            )
        )
    else:
        result = await db.execute(
            select(func.sum(MessageThread.candidate_unread_count)).where(
                MessageThread.candidate_id == current_user.id,
                MessageThread.is_active == True,
            )
        )
    total = result.scalar() or 0
    return {"unread_count": total}


@ws_router.websocket("/api/v1/ws/messages")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.core.dependencies import verify_token
    try:
        user = await verify_token(token, db)
    except Exception:
        await websocket.close(code=4001)
        return
    from backend.messaging.websocket_handler import handle_websocket
    await handle_websocket(websocket, str(user.id))
