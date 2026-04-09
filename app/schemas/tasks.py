"""Pydantic schemas for tasks, submissions, bookmarks, leaderboard, and scores."""

from __future__ import annotations
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


# ── Task schemas ──────────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    id: UUID
    recruiter_id: UUID
    title: str
    slug: str
    description: str
    problem_statement: str
    evaluation_criteria: Any
    domain: str
    difficulty: str
    task_type: str
    submission_types: List[str]
    max_file_size_mb: int
    allowed_file_types: Optional[List[str]] = None
    deadline: datetime
    max_submissions: Optional[int] = None
    is_published: bool
    is_active: bool
    skills_tested: List[str]
    estimated_hours: Optional[float] = None
    company_visible: bool
    company_name: Optional[str] = None
    prize_or_opportunity: Optional[str] = None
    view_count: int
    submission_count: int
    created_at: datetime
    updated_at: datetime
    # Computed fields
    is_bookmarked: bool = False
    candidate_submission_id: Optional[UUID] = None
    candidate_submission_status: Optional[str] = None

    model_config = {"from_attributes": True}


class PaginatedTasksResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ── Submission schemas ────────────────────────────────────────────────────────

class CreateSubmissionRequest(BaseModel):
    task_id: UUID


class UpdateSubmissionRequest(BaseModel):
    text_content: Optional[str] = None
    code_content: Optional[str] = None
    code_language: Optional[str] = None
    file_urls: Optional[List[str]] = None
    link_url: Optional[str] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None
    time_spent_minutes: Optional[int] = None


class SubmissionResponse(BaseModel):
    id: UUID
    task_id: UUID
    candidate_id: UUID
    status: str
    text_content: Optional[str] = None
    code_content: Optional[str] = None
    code_language: Optional[str] = None
    file_urls: Optional[List[str]] = None
    link_url: Optional[str] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    score_accuracy: Optional[float] = None
    score_approach: Optional[float] = None
    score_completeness: Optional[float] = None
    score_efficiency: Optional[float] = None
    total_score: Optional[float] = None
    rank: Optional[int] = None
    percentile: Optional[float] = None
    recruiter_feedback: Optional[str] = None
    ai_summary: Optional[str] = None
    time_spent_minutes: Optional[int] = None
    is_shortlisted: bool
    created_at: datetime
    updated_at: datetime
    task: Optional[TaskResponse] = None

    model_config = {"from_attributes": True}


class PaginatedSubmissionsResponse(BaseModel):
    items: List[SubmissionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ── Leaderboard schemas ───────────────────────────────────────────────────────

class LeaderboardEntryResponse(BaseModel):
    rank: int
    candidate_id: UUID
    candidate_name: str
    candidate_avatar: Optional[str] = None
    total_score: float
    percentile: float
    is_current_user: bool = False
    is_anonymous: bool = False


class LeaderboardResponse(BaseModel):
    task_id: UUID
    task_title: str
    task_domain: str
    total_scored: int
    entries: List[LeaderboardEntryResponse]
    current_user_entry: Optional[LeaderboardEntryResponse] = None


# ── Presigned URL schemas ─────────────────────────────────────────────────────

class PresignedUrlResponse(BaseModel):
    upload_url: str
    file_url: str
    key: str


# ── Skill score schemas ───────────────────────────────────────────────────────

class SkillScoreHistoryItem(BaseModel):
    domain: str
    score: int
    delta: int
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillScoreResponse(BaseModel):
    overall: int
    domains: dict
    percentile: float
    history: List[SkillScoreHistoryItem]


# ── Badge schemas ─────────────────────────────────────────────────────────────

class BadgeResponse(BaseModel):
    id: str
    name: str
    description: str
    earn_condition: str
    earned: bool
    earned_at: Optional[datetime] = None


# ── POW Profile schemas ───────────────────────────────────────────────────────

class ProfileStatsResponse(BaseModel):
    tasks_attempted: int
    tasks_completed: int
    tasks_scored: int
    best_rank: Optional[int] = None
    average_score: Optional[float] = None
    top_10_percent_finishes: int


class POWProfileResponse(BaseModel):
    user: dict
    profile: dict
    stats: ProfileStatsResponse
    skill_score: SkillScoreResponse
    badges: List[BadgeResponse]
    recent_submissions: List[SubmissionResponse]


# ── Bookmark schemas ──────────────────────────────────────────────────────────

class BookmarkToggleRequest(BaseModel):
    task_id: UUID


class BookmarkToggleResponse(BaseModel):
    bookmarked: bool
    task_id: UUID
