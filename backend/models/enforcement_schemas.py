from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CaseStatus(str):
    OPEN = "OPEN"
    INVESTIGATION = "INVESTIGATION"
    PENALTY_REVIEW = "PENALTY_REVIEW"
    NOTICE_ISSUED = "NOTICE_ISSUED"
    HEARING = "HEARING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class CaseSeverity(str):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NoticeType(str):
    SHOW_CAUSE = "SHOW_CAUSE"
    COMPOUNDING_SUMMONS = "COMPOUNDING_SUMMONS"
    SEIZURE_ORDER = "SEIZURE_ORDER"
    PROSECUTION_NOTICE = "PROSECUTION_NOTICE"
    CLOSURE_ORDER = "CLOSURE_ORDER"


class NoticeStatus(str):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SERVED = "SERVED"
    RESPONDED = "RESPONDED"
    DISMISSED = "DISMISSED"


# ── Request / Input Schemas ──────────────────────────────────────────────────

class EnforcementCaseCreate(BaseModel):
    analysis_id: str
    review_id: Optional[str] = None
    product_id: Optional[str] = None
    merchant_organization_id: Optional[str] = None
    violation_summary: Optional[str] = None
    severity: str = CaseSeverity.HIGH
    jurisdiction_state: Optional[str] = None
    jurisdiction_district: Optional[str] = None
    initial_notes: Optional[str] = None


class CaseTransitionRequest(BaseModel):
    to_status: str
    reason: str = Field(..., min_length=3, description="Justification for status transition")
    comments: Optional[str] = None


class CaseAssignmentRequest(BaseModel):
    assigned_officer: str
    comments: Optional[str] = None


class PenaltyCalculationRequest(BaseModel):
    case_id: Optional[str] = None
    repeat_offence: bool = False
    prior_notices: int = 0
    reason: Optional[str] = "Statutory penalty evaluation"


class CreateNoticeForCaseRequest(BaseModel):
    notice_type: str = NoticeType.SHOW_CAUSE
    subject: Optional[str] = None
    officer_name: str = "Legal Metrology Inspector"
    officer_designation: str = "Inspector, Legal Metrology"
    jurisdiction: str = "Consumer Affairs & Legal Metrology Directorate"
    deadline_days: int = Field(default=15, ge=1, le=90)
    recipient_name: Optional[str] = None
    recipient_organization_id: Optional[str] = None
    custom_content: Optional[str] = None


class CaseCloseRequest(BaseModel):
    closure_reason: str = Field(..., min_length=3, description="Mandatory reason for closing enforcement case")
    resolution_type: Optional[str] = "COMPOUNDED"  # COMPOUNDED, COMPLIED, PROSECUTION_INITIATED, DISMISSED, WITHDRAWN
    comments: Optional[str] = None


class CaseReopenRequest(BaseModel):
    reopen_reason: str = Field(..., min_length=3, description="Mandatory reason for reopening enforcement case")
    comments: Optional[str] = None


# ── Output / Response Schemas ────────────────────────────────────────────────

class CaseTimelineEvent(BaseModel):
    event_id: str
    action: str
    actor_username: str
    actor_role: str
    details: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any] = {}


class PenaltyCalculationRecord(BaseModel):
    id: str
    case_id: str
    applicable: bool
    estimated_fine_inr: float
    fine_range_min_inr: float
    fine_range_max_inr: float
    basis: str
    sections: List[str]
    repeat_offence: bool
    prior_notices: int
    violation_count: int
    calculated_by: str
    calculated_at: str
    reason: Optional[str] = None


class EnforcementNoticeResponse(BaseModel):
    id: str
    notice_reference: str
    case_id: str
    notice_type: str
    status: str
    issued_by: str
    issued_at: str
    recipient_organization_id: str
    recipient_name: str
    subject: str
    content: str
    deadline_days: int
    created_at: str
    updated_at: str


class EnforcementCaseSummary(BaseModel):
    id: str
    case_reference: str
    analysis_id: str
    review_id: Optional[str] = None
    product_id: Optional[str] = None
    organization_id: str
    merchant_organization_id: str
    product_name: str
    status: str
    severity: str
    jurisdiction_state: str
    jurisdiction_district: str
    assigned_officer: str
    created_by: str
    opened_at: str
    updated_at: str
    closed_at: Optional[str] = None
    violation_count: int = 0
    notice_count: int = 0


class EnforcementCaseListResponse(BaseModel):
    cases: List[EnforcementCaseSummary]
    total: int
    page: int = 1
    page_size: int = 50


class EnforcementDashboardMetrics(BaseModel):
    open_cases: int
    investigation_cases: int
    penalty_review_cases: int
    notices_issued_cases: int
    hearing_cases: int
    resolved_cases: int
    closed_cases: int
    total_active_cases: int
    assigned_to_me: int
    total_penalties_estimated_inr: float
    total_notices_served: int


class EnforcementCaseDetailResponse(BaseModel):
    id: str
    case_reference: str
    analysis_id: str
    review_id: Optional[str] = None
    product_id: Optional[str] = None
    organization_id: str
    merchant_organization_id: str
    product_name: str
    status: str
    severity: str
    jurisdiction_state: str
    jurisdiction_district: str
    violation_summary: str
    created_by: str
    assigned_officer: str
    opened_at: str
    updated_at: str
    closed_at: Optional[str] = None
    closure_reason: Optional[str] = None
    source_analysis: Optional[Dict[str, Any]] = None
    source_review: Optional[Dict[str, Any]] = None
    violations: List[Dict[str, Any]] = []
    penalties: List[PenaltyCalculationRecord] = []
    notices: List[EnforcementNoticeResponse] = []
    timeline: List[CaseTimelineEvent] = []
