"""MetrCheck AI — Enforcement Case Management & Statutory Notice Ledger API routes.

Phase 4B Architecture:
  - Strict Authorization: Accessible ONLY to ADMIN and ENFORCEMENT_OFFICER (Audit Officers, Merchants, Public Users blocked).
  - Server-enforced Case Lifecycle: OPEN -> INVESTIGATION -> PENALTY_REVIEW -> NOTICE_ISSUED -> HEARING -> RESOLVED -> CLOSED.
  - Persistent, auditable, immutable statutory notice ledger and penalty calculation history.
  - Full case timeline logging and backward-compatible advisory endpoints.
"""
import io
import json
import uuid
import asyncio
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse


from auth.security import (
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
    ROLE_USER,
    get_current_user,
    require_roles,
    check_tenant_access
)

from enforcement.penalties import estimate_penalty, generate_show_cause
from database.db import (
    get_analysis,
    get_review,
    get_review_by_analysis_id,
    get_user_by_username,
    get_all_users,
    save_enforcement_case,
    insert_enforcement_case,
    get_enforcement_case,
    get_enforcement_case_by_analysis_id,
    list_enforcement_cases,
    save_enforcement_notice,
    get_enforcement_notice,
    list_enforcement_notices_by_case,
    save_penalty_calculation,
    list_penalties_by_case,
    get_enforcement_dashboard_metrics,
    generate_case_reference,
    generate_notice_reference,
    log_security_event
)
from models.enforcement_schemas import (
    CaseStatus,
    CaseSeverity,
    NoticeType,
    NoticeStatus,
    EnforcementCaseCreate,
    CaseTransitionRequest,
    CaseAssignmentRequest,
    PenaltyCalculationRequest,
    CreateNoticeForCaseRequest,
    CaseCloseRequest,
    CaseReopenRequest,
    CaseTimelineEvent,
    PenaltyCalculationRecord,
    EnforcementNoticeResponse,
    EnforcementCaseSummary,
    EnforcementCaseListResponse,
    EnforcementDashboardMetrics,
    EnforcementCaseDetailResponse
)

router = APIRouter(prefix="/enforcement", tags=["Enforcement"])

# Strict RBAC dependency for all case management endpoints
ENFORCEMENT_GUARD = Depends(require_roles(ROLE_ADMIN, ROLE_ENFORCEMENT))


# ── Allowed Case Lifecycle Transitions ───────────────────────────────────────
ALLOWED_CASE_TRANSITIONS: Dict[str, List[str]] = {
    CaseStatus.OPEN: [CaseStatus.INVESTIGATION, CaseStatus.PENALTY_REVIEW, CaseStatus.CLOSED],
    CaseStatus.INVESTIGATION: [CaseStatus.PENALTY_REVIEW, CaseStatus.NOTICE_ISSUED, CaseStatus.CLOSED],
    CaseStatus.PENALTY_REVIEW: [CaseStatus.INVESTIGATION, CaseStatus.NOTICE_ISSUED, CaseStatus.HEARING, CaseStatus.CLOSED],
    CaseStatus.NOTICE_ISSUED: [CaseStatus.HEARING, CaseStatus.RESOLVED, CaseStatus.CLOSED],
    CaseStatus.HEARING: [CaseStatus.RESOLVED, CaseStatus.NOTICE_ISSUED, CaseStatus.CLOSED],
    CaseStatus.RESOLVED: [CaseStatus.CLOSED, CaseStatus.OPEN],
    CaseStatus.CLOSED: [CaseStatus.OPEN],  # Reopening transition
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _violations_from_analysis(data: dict) -> list:
    """Convert stored compliance checks into {'severity','what','why','source_reference','rule_id'} dicts."""
    violations = []
    try:
        comp = json.loads(data["compliance_result"]) if isinstance(data["compliance_result"], str) else data.get("compliance_result") or {}
        for c in comp.get("checks", []):
            status_val = (c.get("status") or "").upper()
            if status_val in ("FAIL", "FAILED", "NON_COMPLIANT"):
                violations.append({
                    "severity": "high" if c.get("required", True) else "medium",
                    "rule_id": c.get("rule_id", ""),
                    "what": f"{c.get('field_label') or c.get('field')} — {c.get('reason') or c.get('message') or 'not declared'}",
                    "why": c.get("rule_id", "Legal Metrology (PC) Rules, 2011"),
                    "source_reference": c.get("rule_id", "LMPC Rules, 2011"),
                })
    except Exception:
        pass

    # Include font-size / readability failure if present
    try:
        import ast
        fs = data.get("font_size_analysis") or data.get("font_size_analysis_json")
        if fs:
            if isinstance(fs, str):
                try:
                    fs = json.loads(fs)
                except Exception:
                    fs = ast.literal_eval(fs)
            if isinstance(fs, dict) and (fs.get("rule_12_verdict") or "").startswith("FAIL"):
                violations.append({
                    "severity": "medium",
                    "rule_id": "LM-012",
                    "what": f"Rule 12 font-size violation — net qty font {fs.get('net_quantity_font_height_mm')}mm below required {fs.get('min_required_font_height_mm')}mm",
                    "why": "Rule 12, LMPC Rules, 2011",
                    "source_reference": "Rule 12",
                })
    except Exception:
        pass
    return violations


# ═════════════════════════════════════════════════════════════════════════════
# 1. ENFORCEMENT DASHBOARD & AGGREGATES
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/dashboard",
    response_model=EnforcementDashboardMetrics,
    dependencies=[ENFORCEMENT_GUARD]
)
async def get_enforcement_dashboard(current_user: dict = Depends(get_current_user)):
    """Summary KPI metrics for Enforcement Dashboard."""
    org_id = current_user.get("organization_id")
    if current_user.get("role") == ROLE_ADMIN:
        org_id = None
    return await get_enforcement_dashboard_metrics(
        organization_id=org_id,
        officer_username=current_user.get("username")
    )


@router.get(
    "/officers",
    dependencies=[ENFORCEMENT_GUARD]
)
async def list_available_enforcement_officers(current_user: dict = Depends(get_current_user)):
    """List registered enforcement officers available for enforcement case assignment scoped to tenant."""
    all_users = await get_all_users()
    user_role = current_user.get("role")
    org_id = current_user.get("organization_id")
    officers = [
        {
            "username": u["username"],
            "full_name": u.get("full_name") or u["username"],
            "role": u.get("role", ROLE_ENFORCEMENT),
            "status": u.get("status", "ACTIVE")
        }
        for u in all_users
        if u.get("role") in (ROLE_ADMIN, ROLE_ENFORCEMENT)
        and u.get("status") not in ("SUSPENDED", "DISABLED")
        and (user_role == ROLE_ADMIN or not org_id or u.get("organization_id") == org_id or not u.get("organization_id"))
    ]
    return {"officers": officers, "total": len(officers)}


# ═════════════════════════════════════════════════════════════════════════════
# 2. ENFORCEMENT CASE MANAGEMENT (CRUD & LIFECYCLE)
# ═════════════════════════════════════════════════════════════════════════════

_case_creation_lock = threading.Lock()


@router.post(
    "/cases",
    response_model=EnforcementCaseDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ENFORCEMENT_GUARD]
)
async def create_enforcement_case_endpoint(
    req: EnforcementCaseCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Initiate a formal legal enforcement case from an analysis record.
    Verifies referenced analysis and tenant ownership.
    Uses a threading.Lock to prevent concurrent duplicate case creation.
    """
    loop = asyncio.get_event_loop()

    # Acquire threading lock via executor so we don't block the event loop
    await loop.run_in_executor(None, _case_creation_lock.acquire)
    try:
        analysis = await get_analysis(req.analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Referenced analysis '{req.analysis_id}' not found.")

        # Validate tenant access
        check_tenant_access(current_user, analysis, raise_exception=True)

        # Check if a case already exists for this analysis
        existing = await get_enforcement_case_by_analysis_id(req.analysis_id)
        if existing and existing.get("status") not in (CaseStatus.RESOLVED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=409,
                detail=f"An active enforcement case ({existing.get('case_reference')}) already exists for this analysis."
            )

        now = _now_iso()
        case_id = f"case-{uuid.uuid4().hex[:8]}"
        case_ref = generate_case_reference()

        violations = _violations_from_analysis(analysis)
        viol_count = len(violations)
        auto_summary = req.violation_summary or (
            f"{viol_count} statutory violation(s) identified on '{analysis.get('product_name', 'product')}'"
            if viol_count > 0 else "Routine compliance inspection case"
        )

        timeline_event = {
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "action": "CASE_CREATED",
            "actor_username": current_user.get("username", "officer"),
            "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
            "details": f"Enforcement case initiated. Notes: {req.initial_notes or 'Formal proceeding opened'}",
            "previous_state": None,
            "new_state": CaseStatus.OPEN,
            "timestamp": now,
            "metadata": {"analysis_id": req.analysis_id, "review_id": req.review_id}
        }

        # Authoritative merchant org derived from analysis record
        auth_merchant_org = analysis.get("organization_id", "") or req.merchant_organization_id or ""

        user_jurisdiction = (current_user.get("jurisdiction") or "").strip()
        user_state = current_user.get("state") or ""
        user_district = current_user.get("district_jurisdiction") or ""
        if not user_state and user_jurisdiction:
            if " - " in user_jurisdiction:
                parts = user_jurisdiction.split(" - ", 1)
                user_state = parts[0].strip()
                user_district = parts[1].strip()
            else:
                user_state = user_jurisdiction

        case_record = {
            "id": case_id,
            "case_reference": case_ref,
            "analysis_id": req.analysis_id,
            "review_id": req.review_id or "",
            "product_id": req.product_id or analysis.get("product_id", "") or "",
            "organization_id": current_user.get("organization_id") or "org_ministry",
            "merchant_organization_id": auth_merchant_org,
            "product_name": analysis.get("product_name", "Unknown Product"),
            "status": CaseStatus.OPEN,
            "severity": req.severity or (CaseSeverity.CRITICAL if any(v.get("severity") == "high" for v in violations) else CaseSeverity.HIGH),
            "jurisdiction_state": req.jurisdiction_state or user_state,
            "jurisdiction_district": req.jurisdiction_district or user_district,
            "violation_summary": auto_summary,
            "created_by": current_user.get("username", "officer"),
            "assigned_officer": current_user.get("username", "") if current_user.get("role") == ROLE_ENFORCEMENT else "",
            "opened_at": now,
            "updated_at": now,
            "closed_at": None,
            "closure_reason": "",
            "resolution_type": "",
            "timeline": [timeline_event],
            "created_at": now
        }

        try:
            await insert_enforcement_case(case_record)
        except sqlite3.IntegrityError as db_err:
            # DB-level unique constraint fired (second layer of protection).
            # This can happen if the threading.Lock was somehow bypassed (e.g.
            # multi-process deployment without shared lock).
            raise HTTPException(
                status_code=409,
                detail=(
                    f"An active enforcement case already exists for this analysis "
                    f"(database integrity constraint). [{db_err}]"
                )
            )
        await log_security_event(
            event_type="ENFORCEMENT_CASE_CREATED",
            actor_username=current_user.get("username", "officer"),
            resource_id=case_id,
            details=f"Created case {case_ref} for analysis {req.analysis_id}"
        )
    finally:
        _case_creation_lock.release()

    return await get_enforcement_case_detail_endpoint(case_id, current_user)


@router.get(
    "/cases",
    response_model=EnforcementCaseListResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def list_enforcement_cases_endpoint(
    status: Optional[str] = Query(None, description="Filter by status (e.g. OPEN, INVESTIGATION, NOTICE_ISSUED, CLOSED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    assigned_officer: Optional[str] = Query(None, description="Filter by assigned officer"),
    jurisdiction_state: Optional[str] = Query(None, description="Filter by state"),
    jurisdiction_district: Optional[str] = Query(None, description="Filter by district"),
    merchant_organization_id: Optional[str] = Query(None, description="Filter by merchant org"),
    search: Optional[str] = Query(None, description="Search case ref, product name, or summary"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve server-side filtered, paginated list of enforcement cases.
    """
    offset = (page - 1) * page_size
    user_role = current_user.get("role")
    org_id = current_user.get("organization_id")
    if user_role == ROLE_ADMIN:
        org_id = None

    raw_cases, total_count = await list_enforcement_cases(
        status=status,
        severity=severity,
        assigned_officer=assigned_officer,
        jurisdiction_state=jurisdiction_state,
        jurisdiction_district=jurisdiction_district,
        merchant_organization_id=merchant_organization_id,
        organization_id=org_id,
        search=search,
        limit=page_size,
        offset=offset
    )

    summaries = []
    for c in raw_cases:
        notices = await list_enforcement_notices_by_case(c["id"])
        summaries.append(EnforcementCaseSummary(
            id=c["id"],
            case_reference=c["case_reference"],
            analysis_id=c["analysis_id"],
            review_id=c.get("review_id"),
            product_id=c.get("product_id"),
            organization_id=c.get("organization_id", "org_ministry"),
            merchant_organization_id=c.get("merchant_organization_id", ""),
            product_name=c.get("product_name", ""),
            status=c.get("status", "OPEN"),
            severity=c.get("severity", "HIGH"),
            jurisdiction_state=c.get("jurisdiction_state", ""),
            jurisdiction_district=c.get("jurisdiction_district", ""),
            assigned_officer=c.get("assigned_officer", ""),
            created_by=c.get("created_by", ""),
            opened_at=c.get("opened_at", ""),
            updated_at=c.get("updated_at", ""),
            closed_at=c.get("closed_at"),
            violation_count=0,
            notice_count=len(notices)
        ))

    return EnforcementCaseListResponse(
        cases=summaries,
        total=total_count,
        page=page,
        page_size=page_size
    )


@router.get(
    "/cases/{case_id_or_ref}",
    response_model=EnforcementCaseDetailResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def get_enforcement_case_detail_endpoint(
    case_id_or_ref: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve full case details including violations, notices, penalty history, and timeline.
    """
    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Enforcement case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    # Fetch source analysis
    analysis = await get_analysis(case["analysis_id"])
    violations = _violations_from_analysis(analysis) if analysis else []

    # Fetch source review if linked
    review = None
    if case.get("review_id"):
        raw_rev = await get_review(case["review_id"])
        if raw_rev:
            review = raw_rev

    # Fetch notices & penalty history
    notices_raw = await list_enforcement_notices_by_case(case["id"])
    penalties_raw = await list_penalties_by_case(case["id"])

    notices = [EnforcementNoticeResponse(**n) for n in notices_raw]
    penalties = [
        PenaltyCalculationRecord(
            id=p["id"],
            case_id=p["case_id"],
            applicable=p["applicable"],
            estimated_fine_inr=p["estimated_fine_inr"],
            fine_range_min_inr=p["fine_range_min_inr"],
            fine_range_max_inr=p["fine_range_max_inr"],
            basis=p["basis"],
            sections=p["sections"],
            repeat_offence=p["repeat_offence"],
            prior_notices=p["prior_notices"],
            violation_count=p["violation_count"],
            calculated_by=p["calculated_by"],
            calculated_at=p["calculated_at"],
            reason=p.get("reason")
        )
        for p in penalties_raw
    ]

    raw_timeline = case.get("timeline") or []
    timeline = [CaseTimelineEvent(**t) for t in raw_timeline]

    return EnforcementCaseDetailResponse(
        id=case["id"],
        case_reference=case["case_reference"],
        analysis_id=case["analysis_id"],
        review_id=case.get("review_id"),
        product_id=case.get("product_id"),
        organization_id=case.get("organization_id", "org_ministry"),
        merchant_organization_id=case.get("merchant_organization_id", ""),
        product_name=case.get("product_name", "Unknown Product"),
        status=case.get("status", "OPEN"),
        severity=case.get("severity", "HIGH"),
        jurisdiction_state=case.get("jurisdiction_state", ""),
        jurisdiction_district=case.get("jurisdiction_district", ""),
        violation_summary=case.get("violation_summary", ""),
        created_by=case.get("created_by", ""),
        assigned_officer=case.get("assigned_officer", ""),
        opened_at=case.get("opened_at", ""),
        updated_at=case.get("updated_at", ""),
        closed_at=case.get("closed_at"),
        closure_reason=case.get("closure_reason"),
        source_analysis=analysis,
        source_review=review,
        violations=violations,
        penalties=penalties,
        notices=notices,
        timeline=timeline
    )


@router.post(
    "/cases/{case_id_or_ref}/assign",
    response_model=EnforcementCaseDetailResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def assign_case_endpoint(
    case_id_or_ref: str,
    req: CaseAssignmentRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Assign an enforcement case to a valid enforcement officer or admin.
    Prevents assignment to normal users or merchants.
    """
    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    if case.get("status") == CaseStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot assign a closed case. Reopen the case first.")

    if not req.assigned_officer or not req.assigned_officer.strip():
        raise HTTPException(status_code=400, detail="assigned_officer cannot be empty or whitespace.")

    target_user = await get_user_by_username(req.assigned_officer.strip())
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Officer '{req.assigned_officer}' not found.")

    if target_user.get("role") not in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        raise HTTPException(
            status_code=400,
            detail=f"Target user '{req.assigned_officer}' has role '{target_user.get('role')}'. Enforcement cases can only be assigned to ENFORCEMENT_OFFICER or ADMIN."
        )

    if target_user.get("status") in ("SUSPENDED", "DISABLED"):
        raise HTTPException(status_code=400, detail="Cannot assign case to a suspended or disabled officer.")

    now = _now_iso()
    prev_assigned = case.get("assigned_officer", "unassigned")
    case["assigned_officer"] = req.assigned_officer.strip()
    case["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "CASE_ASSIGNED",
        "actor_username": current_user.get("username", "officer"),
        "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
        "details": f"Case assigned to @{req.assigned_officer.strip()} (previously {prev_assigned}). Notes: {req.comments or 'Assignment updated'}",
        "previous_state": case.get("status"),
        "new_state": case.get("status"),
        "timestamp": now,
        "metadata": {"assigned_officer": req.assigned_officer.strip(), "comments": req.comments}
    }
    case["timeline"].append(event)

    await save_enforcement_case(case)
    return await get_enforcement_case_detail_endpoint(case["id"], current_user)


@router.post(
    "/cases/{case_id_or_ref}/transition",
    response_model=EnforcementCaseDetailResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def transition_case_status_endpoint(
    case_id_or_ref: str,
    req: CaseTransitionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute validated state machine transition for an enforcement case.
    """
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Mandatory reason required for status transition.")

    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    curr_status = case.get("status", CaseStatus.OPEN)
    target_status = req.to_status.upper().strip()

    allowed = ALLOWED_CASE_TRANSITIONS.get(curr_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from '{curr_status}' to '{target_status}'. Allowed transitions: {allowed}"
        )

    now = _now_iso()
    case["status"] = target_status
    case["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "CASE_STATUS_CHANGED",
        "actor_username": current_user.get("username", "officer"),
        "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
        "details": f"Status transitioned to {target_status}. Reason: {req.reason.strip()}. Comments: {req.comments or ''}",
        "previous_state": curr_status,
        "new_state": target_status,
        "timestamp": now,
        "metadata": {"reason": req.reason.strip(), "comments": req.comments}
    }
    case["timeline"].append(event)

    await save_enforcement_case(case)
    return await get_enforcement_case_detail_endpoint(case["id"], current_user)


@router.post(
    "/cases/{case_id_or_ref}/close",
    response_model=EnforcementCaseDetailResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def close_case_endpoint(
    case_id_or_ref: str,
    req: CaseCloseRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Close an enforcement case with mandatory closure reason and resolution classification.
    """
    if not req.closure_reason or not req.closure_reason.strip():
        raise HTTPException(status_code=400, detail="Mandatory closure reason required.")

    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    if case.get("status") == CaseStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Case is already closed.")

    now = _now_iso()
    prev_status = case.get("status", CaseStatus.OPEN)
    case["status"] = CaseStatus.CLOSED
    case["closed_at"] = now
    case["closure_reason"] = req.closure_reason.strip()
    case["resolution_type"] = (req.resolution_type or "COMPOUNDED").strip()
    case["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "CASE_CLOSED",
        "actor_username": current_user.get("username", "officer"),
        "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
        "details": f"Case formally closed ({case['resolution_type']}). Reason: {req.closure_reason.strip()}",
        "previous_state": prev_status,
        "new_state": CaseStatus.CLOSED,
        "timestamp": now,
        "metadata": {"closure_reason": req.closure_reason.strip(), "resolution_type": case["resolution_type"]}
    }
    case["timeline"].append(event)

    await save_enforcement_case(case)
    return await get_enforcement_case_detail_endpoint(case["id"], current_user)


@router.post(
    "/cases/{case_id_or_ref}/reopen",
    response_model=EnforcementCaseDetailResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def reopen_case_endpoint(
    case_id_or_ref: str,
    req: CaseReopenRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Reopen a previously closed or resolved case with recorded justification.
    """
    if not req.reopen_reason or not req.reopen_reason.strip():
        raise HTTPException(status_code=400, detail="Mandatory justification reason required to reopen case.")

    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    if case.get("status") not in (CaseStatus.CLOSED, CaseStatus.RESOLVED):
        raise HTTPException(status_code=400, detail=f"Cannot reopen case in '{case.get('status')}' status. Case must be CLOSED or RESOLVED.")

    now = _now_iso()
    prev_status = case.get("status")
    case["status"] = CaseStatus.OPEN
    case["closed_at"] = None
    case["updated_at"] = now

    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "CASE_REOPENED",
        "actor_username": current_user.get("username", "officer"),
        "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
        "details": f"Case reopened. Justification: {req.reopen_reason.strip()}. Comments: {req.comments or ''}",
        "previous_state": prev_status,
        "new_state": CaseStatus.OPEN,
        "timestamp": now,
        "metadata": {"reopen_reason": req.reopen_reason.strip(), "comments": req.comments}
    }
    case["timeline"].append(event)

    await save_enforcement_case(case)
    return await get_enforcement_case_detail_endpoint(case["id"], current_user)


# ═════════════════════════════════════════════════════════════════════════════
# 3. PENALTY CALCULATION & PERSISTENCE
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/cases/{case_id_or_ref}/calculate-penalty",
    response_model=PenaltyCalculationRecord,
    dependencies=[ENFORCEMENT_GUARD]
)
async def calculate_and_save_case_penalty(
    case_id_or_ref: str,
    req: PenaltyCalculationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Calculates statutory penalty under Legal Metrology Act, 2009 Sec 36/38,
    and persistently stores an immutable calculation record on the case timeline.
    """
    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    if case.get("status") == CaseStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot calculate penalty for a closed case.")

    analysis = await get_analysis(case["analysis_id"])
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis '{case['analysis_id']}' not found.")

    violations = _violations_from_analysis(analysis)
    calc_res = estimate_penalty(
        violations,
        repeat_offence=req.repeat_offence,
        prior_notices=req.prior_notices,
    )

    now = _now_iso()
    pen_id = f"pen-{uuid.uuid4().hex[:8]}"
    f_min = float(calc_res["fine_range_inr"][0])
    f_max = float(calc_res["fine_range_inr"][1])

    pen_record = {
        "id": pen_id,
        "case_id": case["id"],
        "analysis_id": case["analysis_id"],
        "applicable": calc_res["applicable"],
        "estimated_fine_inr": float(calc_res["estimated_fine_inr"]),
        "fine_range_min_inr": f_min,
        "fine_range_max_inr": f_max,
        "basis": calc_res["basis"],
        "sections": calc_res["sections"],
        "repeat_offence": req.repeat_offence,
        "prior_notices": req.prior_notices,
        "violation_count": calc_res["violation_count"],
        "calculated_by": current_user.get("username", "officer"),
        "calculated_at": now,
        "reason": req.reason or "Statutory penalty evaluation",
        "created_at": now
    }

    await save_penalty_calculation(pen_record)

    # Append to case timeline
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "PENALTY_CALCULATED",
        "actor_username": current_user.get("username", "officer"),
        "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
        "details": f"Statutory penalty calculated: ₹{calc_res['estimated_fine_inr']:,} (Range: ₹{f_min:,} - ₹{f_max:,}). Basis: {calc_res['basis']}",
        "previous_state": case.get("status"),
        "new_state": CaseStatus.PENALTY_REVIEW if case.get("status") in (CaseStatus.OPEN, CaseStatus.INVESTIGATION) else case.get("status"),
        "timestamp": now,
        "metadata": {
            "penalty_id": pen_id,
            "estimated_fine_inr": calc_res["estimated_fine_inr"],
            "repeat_offence": req.repeat_offence
        }
    }
    case["timeline"].append(event)
    if case.get("status") in (CaseStatus.OPEN, CaseStatus.INVESTIGATION):
        case["status"] = CaseStatus.PENALTY_REVIEW
    case["updated_at"] = now

    await save_enforcement_case(case)

    return PenaltyCalculationRecord(
        id=pen_id,
        case_id=case["id"],
        applicable=calc_res["applicable"],
        estimated_fine_inr=float(calc_res["estimated_fine_inr"]),
        fine_range_min_inr=f_min,
        fine_range_max_inr=f_max,
        basis=calc_res["basis"],
        sections=calc_res["sections"],
        repeat_offence=req.repeat_offence,
        prior_notices=req.prior_notices,
        violation_count=calc_res["violation_count"],
        calculated_by=current_user.get("username", "officer"),
        calculated_at=now,
        reason=req.reason
    )


# ═════════════════════════════════════════════════════════════════════════════
# 4. STATUTORY NOTICE LEDGER & PERSISTENCE
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/cases/{case_id_or_ref}/notices",
    response_model=EnforcementNoticeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ENFORCEMENT_GUARD]
)
async def create_notice_for_case_endpoint(
    case_id_or_ref: str,
    req: CreateNoticeForCaseRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Issue and persistently archive a statutory notice (e.g. Show-Cause Notice) under an enforcement case.
    """
    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    if case.get("status") == CaseStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot issue a notice under a closed case.")

    analysis = await get_analysis(case["analysis_id"])
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis '{case['analysis_id']}' not found.")

    violations = _violations_from_analysis(analysis)
    
    # Notice content generation
    if req.custom_content:
        content = req.custom_content
    else:
        content = generate_show_cause(
            analysis_id=case["analysis_id"],
            product_name=case.get("product_name") or analysis.get("product_name", "Product"),
            manufacturer=analysis.get("manufacturer") or case.get("product_name") or "Manufacturer/Packer",
            violations=violations,
            officer_name=req.officer_name,
            officer_designation=req.officer_designation,
            jurisdiction=req.jurisdiction,
            deadline_days=req.deadline_days,
        )

    now = _now_iso()
    notice_id = f"not-{uuid.uuid4().hex[:8]}"
    notice_ref = generate_notice_reference(req.notice_type)

    notice_record = {
        "id": notice_id,
        "notice_reference": notice_ref,
        "case_id": case["id"],
        "notice_type": req.notice_type or NoticeType.SHOW_CAUSE,
        "status": NoticeStatus.ISSUED,
        "issued_by": current_user.get("username", "officer"),
        "issued_at": now,
        "recipient_organization_id": req.recipient_organization_id or case.get("merchant_organization_id", ""),
        "recipient_name": req.recipient_name or analysis.get("manufacturer") or case.get("product_name", "Manufacturer"),
        "subject": req.subject or f"Statutory Show Cause Notice — {case['case_reference']}",
        "content": content,
        "deadline_days": req.deadline_days,
        "created_at": now,
        "updated_at": now
    }

    await save_enforcement_notice(notice_record)

    # Timeline event & state transition
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "action": "NOTICE_ISSUED",
        "actor_username": current_user.get("username", "officer"),
        "actor_role": current_user.get("role", ROLE_ENFORCEMENT),
        "details": f"Statutory notice issued: {notice_ref} ({req.notice_type}). Response deadline: {req.deadline_days} days.",
        "previous_state": case.get("status"),
        "new_state": CaseStatus.NOTICE_ISSUED,
        "timestamp": now,
        "metadata": {"notice_id": notice_id, "notice_reference": notice_ref, "notice_type": req.notice_type}
    }
    case["timeline"].append(event)
    case["status"] = CaseStatus.NOTICE_ISSUED
    case["updated_at"] = now

    await save_enforcement_case(case)
    await log_security_event(
        event_type="STATUTORY_NOTICE_ISSUED",
        actor_username=current_user.get("username", "officer"),
        resource_id=notice_id,
        details=f"Issued notice {notice_ref} for case {case['case_reference']}"
    )

    return EnforcementNoticeResponse(**notice_record)


@router.get(
    "/cases/{case_id_or_ref}/notices",
    response_model=List[EnforcementNoticeResponse],
    dependencies=[ENFORCEMENT_GUARD]
)
async def list_case_notices_endpoint(
    case_id_or_ref: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve all statutory notices issued under a specific case.
    """
    case = await get_enforcement_case(case_id_or_ref)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id_or_ref}' not found.")

    check_tenant_access(current_user, case, raise_exception=True)

    notices = await list_enforcement_notices_by_case(case["id"])
    return [EnforcementNoticeResponse(**n) for n in notices]


@router.get(
    "/notices/{notice_id_or_ref}",
    response_model=EnforcementNoticeResponse,
    dependencies=[ENFORCEMENT_GUARD]
)
async def get_notice_detail_endpoint(
    notice_id_or_ref: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve full details and content of a specific statutory notice.
    """
    notice = await get_enforcement_notice(notice_id_or_ref)
    if not notice:
        raise HTTPException(status_code=404, detail=f"Notice '{notice_id_or_ref}' not found.")

    case = await get_enforcement_case(notice["case_id"])
    if case:
        check_tenant_access(current_user, case, raise_exception=True)
    else:
        if current_user.get("role") != ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot verify parent case tenant authorization."
            )

    return EnforcementNoticeResponse(**notice)


# ═════════════════════════════════════════════════════════════════════════════
# 5. BACKWARD-COMPATIBLE ADVISORY ENDPOINTS (PRESERVED)
# ═════════════════════════════════════════════════════════════════════════════

class PenaltyRequest(BaseModel):
    analysis_id: str
    repeat_offence: bool = False
    prior_notices: int = 0


class NoticeRequest(BaseModel):
    analysis_id: str
    officer_name: str = "Legal Metrology Inspector"
    officer_designation: str = "Inspector, Legal Metrology"
    jurisdiction: str = "Consumer Affairs & Legal Metrology Directorate"
    deadline_days: int = Field(default=15, ge=1, le=90)


@router.post("/penalty")
async def penalty_estimate_compat(req: PenaltyRequest, user: dict = Depends(get_current_user)):
    """Backward-compatible penalty calculation endpoint."""
    if user["role"] not in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        raise HTTPException(status_code=403, detail="Enforcement or Admin role required.")
    data = await get_analysis(req.analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    check_tenant_access(user, data, raise_exception=True)

    violations = _violations_from_analysis(data)
    result = estimate_penalty(
        violations,
        repeat_offence=req.repeat_offence,
        prior_notices=req.prior_notices,
    )
    result["analysis_id"] = req.analysis_id
    result["product_name"] = data.get("product_name", "Unknown product")
    result["violations"] = violations
    result["issued_by"] = user.get("username")

    # If linked to a case, persist automatically
    try:
        case = await get_enforcement_case_by_analysis_id(req.analysis_id)
        if case and case.get("status") != CaseStatus.CLOSED:
            now = _now_iso()
            pen_id = f"pen-{uuid.uuid4().hex[:8]}"
            await save_penalty_calculation({
                "id": pen_id,
                "case_id": case["id"],
                "analysis_id": req.analysis_id,
                "applicable": result["applicable"],
                "estimated_fine_inr": float(result["estimated_fine_inr"]),
                "fine_range_min_inr": float(result["fine_range_inr"][0]),
                "fine_range_max_inr": float(result["fine_range_inr"][1]),
                "basis": result["basis"],
                "sections": result["sections"],
                "repeat_offence": req.repeat_offence,
                "prior_notices": req.prior_notices,
                "violation_count": result["violation_count"],
                "calculated_by": user.get("username", "officer"),
                "calculated_at": now,
                "reason": "Direct /penalty endpoint evaluation",
                "created_at": now
            })
            result["case_id"] = case["id"]
            result["case_reference"] = case["case_reference"]
            result["penalty_record_id"] = pen_id
    except Exception:
        pass

    return result


@router.post("/notice")
async def show_cause_compat(req: NoticeRequest, user: dict = Depends(get_current_user)):
    """Backward-compatible notice generation endpoint."""
    if user["role"] not in (ROLE_ADMIN, ROLE_ENFORCEMENT):
        raise HTTPException(status_code=403, detail="Enforcement or Admin role required.")
    data = await get_analysis(req.analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    check_tenant_access(user, data, raise_exception=True)

    violations = _violations_from_analysis(data)
    if not violations:
        return {
            "notice": "No violations recorded for this analysis — show-cause notice is not applicable.",
            "analysis_id": req.analysis_id,
        }

    notice = generate_show_cause(
        analysis_id=req.analysis_id,
        product_name=data.get("product_name", "Unknown product"),
        manufacturer=data.get("manufacturer") or data.get("product_name") or "Manufacturer",
        violations=violations,
        officer_name=req.officer_name,
        officer_designation=req.officer_designation,
        jurisdiction=req.jurisdiction,
        deadline_days=req.deadline_days,
    )

    resp = {
        "notice": notice,
        "analysis_id": req.analysis_id,
        "generated_by": user.get("username")
    }

    # If linked to a case, persist automatically
    try:
        case = await get_enforcement_case_by_analysis_id(req.analysis_id)
        if case and case.get("status") != CaseStatus.CLOSED:
            now = _now_iso()
            n_id = f"not-{uuid.uuid4().hex[:8]}"
            n_ref = generate_notice_reference("SHOW_CAUSE")
            await save_enforcement_notice({
                "id": n_id,
                "notice_reference": n_ref,
                "case_id": case["id"],
                "notice_type": NoticeType.SHOW_CAUSE,
                "status": NoticeStatus.ISSUED,
                "issued_by": user.get("username", "officer"),
                "issued_at": now,
                "recipient_organization_id": case.get("merchant_organization_id", ""),
                "recipient_name": data.get("manufacturer") or case.get("product_name", "Manufacturer"),
                "subject": f"Statutory Show Cause Notice — {case['case_reference']}",
                "content": notice,
                "deadline_days": req.deadline_days,
                "created_at": now,
                "updated_at": now
            })
            resp["case_id"] = case["id"]
            resp["case_reference"] = case["case_reference"]
            resp["notice_id"] = n_id
            resp["notice_reference"] = n_ref
    except Exception:
        pass

    return resp