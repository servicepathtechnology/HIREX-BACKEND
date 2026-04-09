"""Admin panel — FastAPI router with session-based auth and audit logging."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.part5 import AdminAuditLog, AdminUser
from app.models.recruiter import PipelineEntry, TaskPayment
from app.models.task import Submission, Task
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Simple in-memory session store (use Redis in production)
_sessions: dict[str, dict] = {}
SESSION_TTL_HOURS = 8


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _create_session(email: str) -> str:
    import secrets
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"email": email, "created_at": datetime.utcnow()}
    return token


def _get_session(token: Optional[str]) -> Optional[dict]:
    if not token or token not in _sessions:
        return None
    session = _sessions[token]
    if datetime.utcnow() - session["created_at"] > timedelta(hours=SESSION_TTL_HOURS):
        del _sessions[token]
        return None
    return session


async def get_admin_session(
    admin_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = _get_session(admin_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin login required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session


async def _log_action(
    db: AsyncSession,
    admin_email: str,
    action: str,
    target_type: str,
    target_id: Optional[UUID] = None,
    details: Optional[dict] = None,
) -> None:
    log = AdminAuditLog(
        admin_email=admin_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(log)
    await db.flush()


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page() -> HTMLResponse:
    return HTMLResponse(_login_html())


@router.post("/login")
async def admin_login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    result = await db.execute(select(AdminUser).where(AdminUser.email == email, AdminUser.is_active == True))
    admin = result.scalar_one_or_none()
    if not admin or not bcrypt.checkpw(password.encode(), admin.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    token = _create_session(email)
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.set_cookie("admin_token", token, httponly=True, max_age=SESSION_TTL_HOURS * 3600)
    return response


@router.get("/logout")
async def admin_logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_token")
    return response


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    session: dict = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    total_submissions = (await db.execute(select(func.count(Submission.id)))).scalar() or 0
    total_hires = (await db.execute(
        select(func.count(PipelineEntry.id)).where(PipelineEntry.stage == "hired")
    )).scalar() or 0
    total_revenue_paise = (await db.execute(
        select(func.sum(TaskPayment.amount_paise)).where(TaskPayment.status == "paid")
    )).scalar() or 0
    mrr_inr = total_revenue_paise / 100

    stats = {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "total_submissions": total_submissions,
        "total_hires": total_hires,
        "mrr_inr": f"₹{mrr_inr:,.0f}",
    }
    return HTMLResponse(_dashboard_html(stats, session["email"]))


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    search: str = "",
    page: int = 1,
    session: dict = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    query = select(User).order_by(User.created_at.desc())
    if search:
        query = query.where(User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%"))
    result = await db.execute(query.offset((page - 1) * 20).limit(20))
    users = result.scalars().all()
    return HTMLResponse(_users_html(users, search, session["email"]))


@router.post("/users/{user_id}/suspend")
async def admin_suspend_user(
    user_id: UUID,
    session: dict = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_suspended = True
    await _log_action(db, session["email"], "suspend_user", "user", user_id, {"email": user.email})
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/unsuspend")
async def admin_unsuspend_user(
    user_id: UUID,
    session: dict = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_suspended = False
    await _log_action(db, session["email"], "unsuspend_user", "user", user_id, {"email": user.email})
    return RedirectResponse(url="/admin/users", status_code=302)


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/audit-log", response_class=HTMLResponse)
async def admin_audit_log(
    session: dict = Depends(get_admin_session),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    result = await db.execute(
        select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(100)
    )
    logs = result.scalars().all()
    return HTMLResponse(_audit_log_html(logs, session["email"]))


# ── HTML templates (minimal Jinja2-free HTML) ─────────────────────────────────

def _base_html(title: str, content: str, admin_email: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>HireX Admin — {title}</title>
<style>
  body{{font-family:system-ui,sans-serif;margin:0;background:#0f172a;color:#f8fafc}}
  nav{{background:#1e293b;padding:12px 24px;display:flex;gap:16px;align-items:center}}
  nav a{{color:#94a3b8;text-decoration:none;font-size:14px}}nav a:hover{{color:#f8fafc}}
  .badge{{background:#6366f1;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px}}
  main{{padding:24px}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #1e293b}}
  th{{background:#1e293b;color:#94a3b8}}
  .card{{background:#1e293b;border-radius:8px;padding:20px;margin-bottom:16px}}
  .stat{{font-size:32px;font-weight:700;color:#6366f1}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}}
  .btn{{background:#6366f1;color:#fff;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:13px}}
  .btn-red{{background:#ef4444}}
  input[type=text],input[type=email],input[type=password]{{background:#0f172a;border:1px solid #334155;color:#f8fafc;padding:8px 12px;border-radius:4px;width:100%;box-sizing:border-box}}
</style></head>
<body>
<nav>
  <span style="color:#6366f1;font-weight:700;font-size:18px">HireX Admin</span>
  <a href="/admin/dashboard">Dashboard</a>
  <a href="/admin/users">Users</a>
  <a href="/admin/audit-log">Audit Log</a>
  <span style="margin-left:auto;color:#64748b;font-size:13px">{admin_email}</span>
  <a href="/admin/logout">Logout</a>
</nav>
<main>{content}</main>
</body></html>"""


def _login_html() -> str:
    return """<!DOCTYPE html>
<html><head><title>HireX Admin Login</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#1e293b;padding:40px;border-radius:12px;width:360px}
h2{margin:0 0 24px;color:#6366f1}
label{display:block;margin-bottom:4px;font-size:13px;color:#94a3b8}
input{background:#0f172a;border:1px solid #334155;color:#f8fafc;padding:10px 12px;border-radius:4px;width:100%;box-sizing:border-box;margin-bottom:16px}
button{background:#6366f1;color:#fff;border:none;padding:12px;border-radius:4px;width:100%;cursor:pointer;font-size:15px}
</style></head>
<body><div class="card">
<h2>HireX Admin</h2>
<form method="post" action="/admin/login">
<label>Email</label><input type="email" name="email" required>
<label>Password</label><input type="password" name="password" required>
<button type="submit">Login</button>
</form></div></body></html>"""


def _dashboard_html(stats: dict, admin_email: str) -> str:
    content = f"""<h2>Dashboard</h2>
<div class="grid">
  <div class="card"><div class="stat">{stats['total_users']}</div><div>Total Users</div></div>
  <div class="card"><div class="stat">{stats['total_tasks']}</div><div>Total Tasks</div></div>
  <div class="card"><div class="stat">{stats['total_submissions']}</div><div>Submissions</div></div>
  <div class="card"><div class="stat">{stats['total_hires']}</div><div>Verified Hires</div></div>
  <div class="card"><div class="stat">{stats['mrr_inr']}</div><div>Total Revenue</div></div>
</div>"""
    return _base_html("Dashboard", content, admin_email)


def _users_html(users: list, search: str, admin_email: str) -> str:
    rows = ""
    for u in users:
        suspended = "✓" if getattr(u, "is_suspended", False) else ""
        rows += f"""<tr>
<td>{u.email}</td><td>{u.full_name}</td><td>{u.role or '—'}</td>
<td>{suspended}</td><td>{u.created_at.strftime('%Y-%m-%d')}</td>
<td>
  <form method="post" action="/admin/users/{u.id}/suspend" style="display:inline">
    <button class="btn btn-red" type="submit">Suspend</button>
  </form>
  <form method="post" action="/admin/users/{u.id}/unsuspend" style="display:inline">
    <button class="btn" type="submit">Unsuspend</button>
  </form>
</td></tr>"""

    content = f"""<h2>Users</h2>
<form method="get" style="margin-bottom:16px">
  <input type="text" name="search" value="{search}" placeholder="Search by email or name" style="width:300px">
  <button class="btn" type="submit" style="margin-left:8px">Search</button>
</form>
<table><thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Suspended</th><th>Joined</th><th>Actions</th></tr></thead>
<tbody>{rows}</tbody></table>"""
    return _base_html("Users", content, admin_email)


def _audit_log_html(logs: list, admin_email: str) -> str:
    rows = ""
    for log in logs:
        rows += f"""<tr>
<td>{log.created_at.strftime('%Y-%m-%d %H:%M')}</td>
<td>{log.admin_email}</td><td>{log.action}</td>
<td>{log.target_type}</td><td>{str(log.target_id)[:8] if log.target_id else '—'}</td>
</tr>"""
    content = f"""<h2>Audit Log</h2>
<table><thead><tr><th>Time</th><th>Admin</th><th>Action</th><th>Target Type</th><th>Target ID</th></tr></thead>
<tbody>{rows}</tbody></table>"""
    return _base_html("Audit Log", content, admin_email)
