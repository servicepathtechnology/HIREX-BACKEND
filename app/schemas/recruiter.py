"""Pydantic schemas for Part 3 — recruiter tasks, scoring, pipeline, billing, analytics, notifications."""

from __future__ import annotations
from typing import Optional, List, Any, Dict
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


# ── Recruiter Task schemas ────────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    title: str
    domain: str
    task_type: str
    difficulty: str
    skills_tested: List[str]
    description: str = ""
    problem_statement: str = ""
    context_background: Optional[str] = None
    evaluation_criteria: Optional[List[Dict[str, Any]]] = None
    deadline: Optional[datetime] = None
    submission_types: List[str] = []
    allowed_file_types: Optional[List[str]] = None
    max_file_size_mb: int = 10
    max_submissions: Optional[int] = None
    company_visible: bool = True
    company_name: Optional[str] = None
    prize_or_opportunity: Optional[str] = None
    estimated_hours: Optional[float] = None
    tier: str = "standard"


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    domain: Optional[str] = None
    task_type: Optional[str] = None
    difficulty: Optional[str] = None
    skills_tested: Optional[List[str]] = None
    description: Optional[str] = None
    problem_statement: Optional[str] = None
    context_background: Optional[str] = None
    evaluation_criteria: Optional[List[Dict[str, Any]]] = None
    deadline: Optional[datetime] = None
    submission_types: Optional[List[str]] = None
    allowed_file_types: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    max_submissions: Optional[int] = None
    company_visible: Optional[bool] = None
    company_name: Optional[str] = None
    prize_or_opportunity: Optional[str] = None
    estimated_hours: Optional[float] = None
    tier: Optional[str] = None
    is_published: Optional[bool] = None
    is_active: Optional[bool] = None


class RecruiterTaskResponse(BaseModel):
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
    deadline: Optional[datetime] = None
    max_submissions: Optional[int] = None
    is_published: bool
    is_active: bool
    skills_tested: List[str]
    estimated_hours: Optional[float] = None
    company_visible: bool
    company_name: Optional[str] = None
    prize_or_opportunity: Optional[str] = None
    tier: str
    view_count: int
    submission_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedRecruiterTasksResponse(BaseModel):
    items: List[RecruiterTaskResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class TaskStatsResponse(BaseModel):
    task_id: UUID
    total_submissions: int
    pending_review: int
    scored: int
    shortlisted: int
    hired: int
    avg_score: Optional[float] = None


# ── Scoring schemas ───────────────────────────────────────────────────────────

class CriterionScore(BaseModel):
    criterion_name: str
    score: float  # 0-100
    weight: float  # 0-100 (percentage)


class ScoreSubmissionRequest(BaseModel):
    criterion_scores: List[CriterionScore]
    recruiter_feedback: Optional[str] = None
    shortlist: bool = False


class RecruiterSubmissionResponse(BaseModel):
    id: UUID
    task_id: UUID
    candidate_id: UUID
    candidate_name: Optional[str] = None
    candidate_avatar: Optional[str] = None
    status: str
    text_content: Optional[str] = None
    code_content: Optional[str] = None
    code_language: Optional[str] = None
    file_urls: Optional[List[str]] = None
    link_url: Optional[str] = None
    recording_url: Optional[str] = None
    notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    total_score: Optional[float] = None
    rank: Optional[int] = None
    percentile: Optional[float] = None
    recruiter_feedback: Optional[str] = None
    time_spent_minutes: Optional[int] = None
    is_shortlisted: bool
    criterion_scores: Optional[List[Dict[str, Any]]] = None
    ai_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedRecruiterSubmissionsResponse(BaseModel):
    items: List[RecruiterSubmissionResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ── Pipeline schemas ──────────────────────────────────────────────────────────

class PipelineEntryResponse(BaseModel):
    id: UUID
    recruiter_id: UUID
    candidate_id: UUID
    candidate_name: Optional[str] = None
    candidate_avatar: Optional[str] = None
    task_id: UUID
    task_title: Optional[str] = None
    task_domain: Optional[str] = None
    submission_id: UUID
    total_score: Optional[float] = None
    rank: Optional[int] = None
    stage: str
    recruiter_notes: Optional[str] = None
    stage_updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdatePipelineStageRequest(BaseModel):
    stage: str


class UpdatePipelineNotesRequest(BaseModel):
    recruiter_notes: str


class PipelineBoardResponse(BaseModel):
    shortlisted: List[PipelineEntryResponse]
    interviewing: List[PipelineEntryResponse]
    offer_sent: List[PipelineEntryResponse]
    hired: List[PipelineEntryResponse]
    rejected: List[PipelineEntryResponse]


# ── Billing schemas ───────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    task_id: UUID
    tier: str


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
    task_id: UUID
    tier: str


class VerifyPaymentRequest(BaseModel):
    order_id: str
    payment_id: str
    signature: str


class VerifyPaymentResponse(BaseModel):
    success: bool
    task_id: UUID
    message: str


class PaymentHistoryResponse(BaseModel):
    id: UUID
    task_id: UUID
    task_title: Optional[str] = None
    tier: str
    amount_paise: int
    currency: str
    status: str
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedPaymentHistoryResponse(BaseModel):
    items: List[PaymentHistoryResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ── Analytics schemas ─────────────────────────────────────────────────────────

class SubmissionTimelinePoint(BaseModel):
    date: str
    count: int


class AnalyticsResponse(BaseModel):
    task_id: Optional[UUID] = None
    total_views: int
    total_submissions: int
    scored_count: int
    shortlisted_count: int
    hired_count: int
    avg_score: Optional[float] = None
    score_distribution: Optional[Dict[str, int]] = None
    avg_time_spent_mins: Optional[float] = None
    time_to_first_submission_hours: Optional[float] = None
    conversion_rate: Optional[float] = None
    submission_timeline: List[SubmissionTimelinePoint] = []


# ── Notification schemas ──────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedNotificationsResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class UnreadCountResponse(BaseModel):
    count: int


# ── Dashboard schemas ─────────────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    active_tasks: int
    total_submissions: int
    pending_review: int
    hires_made: int


class RecentSubmissionItem(BaseModel):
    submission_id: UUID
    task_id: UUID
    task_title: str
    candidate_name: Optional[str] = None
    candidate_avatar: Optional[str] = None
    submitted_at: Optional[datetime] = None
    status: str


class RecruiterDashboardResponse(BaseModel):
    stats: DashboardStatsResponse
    active_tasks: List[RecruiterTaskResponse]
    recent_submissions: List[RecentSubmissionItem]
