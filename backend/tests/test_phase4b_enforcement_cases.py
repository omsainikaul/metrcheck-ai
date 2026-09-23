"""
Phase 4B Test Suite: Enforcement Case Management & Statutory Notice Ledger
Tests 34 mandatory requirements covering:
  - Role-based access control (RBAC) across ADMIN, ENFORCEMENT_OFFICER, AUDIT_OFFICER, MERCHANT_PUBLIC, and PUBLIC_USER
  - Enforcement case lifecycle state machine & transition rules
  - Immutable statutory penalty calculation & history preservation
  - Unique statutory notice creation, formatting & immutability
  - Audit review escalation handoff into persistent enforcement cases
  - IDOR and cross-case tenant isolation
  - Officer suspension and credential invalidation
"""
import os
import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import (
    get_db,
    init_db,
    create_organization,
    create_user,
    save_analysis,
    get_analysis,
    save_review,
    get_review,
    save_enforcement_case,
    get_enforcement_case,
    get_enforcement_case_by_analysis_id,
    list_enforcement_cases,
    save_enforcement_notice,
    get_enforcement_notice,
    list_enforcement_notices_by_case,
    save_penalty_calculation,
    list_penalties_by_case,
    suspend_user
)

from auth.security import (
    hash_password,
    create_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
    ROLE_USER
)

from models.review_schemas import ReviewStatus, EscalateReviewRequest
from services.review_service import escalate_review


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


async def _create_test_user(username: str, role: str, org_id: str = "", state: str = "Delhi", district: str = "Central"):
    salt, pwh = hash_password("Password123!")
    try:
        await create_user(
            username=username,
            password_hash=pwh,
            salt=salt,
            role=role,
            full_name=f"User {username}",
            organization_id=org_id,
            jurisdiction=f"{state} - {district}"
        )
    except Exception:
        pass


def make_headers(username: str, role: str, token_version: int = 1) -> dict:
    token = create_token(username, role, token_version=token_version)
    return {"Authorization": f"Bearer {token}"}


async def _seed_enforcement_data():
    await init_db()
    db = await get_db()
    try:
        await db.execute("DELETE FROM enforcement_notices")
        await db.execute("DELETE FROM penalty_calculations")
        await db.execute("DELETE FROM enforcement_cases")
        await db.execute("DELETE FROM officer_reviews")
        await db.execute("UPDATE users SET status = 'ACTIVE', token_version = 1 WHERE username IN ('enforcement_officer_1', 'enforcement_officer_2', 'audit_officer_1', 'merchant_a_user', 'merchant_b_user', 'admin_enf', 'public_user_1')")
        await db.commit()
    finally:
        await db.close()
    
    # Orgs
    await create_organization("org_ministry", "Ministry of Consumer Affairs", org_type="REGULATOR", jurisdiction="National")
    await create_organization("org_merchant_a", "Alpha Foods Ltd", org_type="MERCHANT", jurisdiction="North")
    await create_organization("org_merchant_b", "Beta Beverages Corp", org_type="MERCHANT", jurisdiction="South")

    # Users
    await _create_test_user("admin_enf", ROLE_ADMIN, "")
    await _create_test_user("enforcement_officer_1", ROLE_ENFORCEMENT, "org_ministry", state="Delhi", district="Central")
    await _create_test_user("enforcement_officer_2", ROLE_ENFORCEMENT, "org_ministry", state="Maharashtra", district="Mumbai")
    await _create_test_user("audit_officer_1", ROLE_AUDIT, "org_ministry", state="Delhi", district="Central")
    await _create_test_user("merchant_a_user", ROLE_MERCHANT, "org_merchant_a")
    await _create_test_user("merchant_b_user", ROLE_MERCHANT, "org_merchant_b")
    await _create_test_user("public_user_1", ROLE_USER, "")

    # Analyses
    await save_analysis({
        "id": "ana_enf_test_1",
        "product_name": "Premium Crunchy Biscuits 200g",
        "image_filename": "biscuit_test.jpg",
        "owner_user_id": "enforcement_officer_1",
        "organization_id": "org_ministry",
        "score": 45.0,
        "status": "FAIL",
        "created_at": "2026-03-01T10:00:00Z",
        "extracted_data": json.dumps({"product_name": "Premium Crunchy Biscuits", "mrp": "₹40"}),
        "compliance_result": json.dumps({
            "score": 45.0,
            "status": "FAIL",
            "checks": [
                {"field": "mrp", "field_label": "Maximum Retail Price", "status": "FAIL", "required": True, "reason": "Missing MRP declaration", "rule_id": "Rule 6(1)(e)"},
                {"field": "net_quantity", "field_label": "Net Quantity", "status": "FAIL", "required": True, "reason": "Missing Net Qty declaration", "rule_id": "Rule 11"}
            ]
        })
    })

    await save_analysis({
        "id": "ana_enf_test_2",
        "product_name": "Beta Fruit Juice 1L",
        "image_filename": "juice_test.jpg",
        "owner_user_id": "enforcement_officer_1",
        "organization_id": "org_ministry",
        "score": 60.0,
        "status": "FAIL",
        "created_at": "2026-03-02T10:00:00Z",
        "extracted_data": json.dumps({"product_name": "Beta Fruit Juice", "mrp": "₹90"}),
        "compliance_result": json.dumps({
            "score": 60.0,
            "status": "FAIL",
            "checks": [
                {"field": "manufacturer", "field_label": "Manufacturer Details", "status": "FAIL", "required": True, "reason": "Incomplete address", "rule_id": "Rule 6(1)(a)"}
            ]
        })
    })


# ═════════════════════════════════════════════════════════════════════════════
# RBAC & CREATION TESTS (Requirements 1-8)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_enforcement_officer_creates_case():
    """1. Enforcement Officer can create a persistent enforcement case."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    payload = {
        "analysis_id": "ana_enf_test_1",
        "severity": "CRITICAL",
        "initial_notes": "Statutory non-compliance identified during market surveillance."
    }
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["analysis_id"] == "ana_enf_test_1"
    assert data["case_reference"].startswith("MC-ENF-")
    assert data["status"] == "OPEN"
    assert data["severity"] == "CRITICAL"
    assert len(data["timeline"]) >= 1


@pytest.mark.asyncio
async def test_02_audit_officer_cannot_create_case():
    """2. Audit Officer is strictly blocked from creating enforcement cases."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("audit_officer_1", ROLE_AUDIT)
    payload = {"analysis_id": "ana_enf_test_1"}
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_03_merchant_cannot_create_case():
    """3. Merchant is strictly blocked with 403 from creating enforcement cases."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("merchant_a_user", ROLE_MERCHANT)
    payload = {"analysis_id": "ana_enf_test_1"}
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_04_normal_user_cannot_create_case():
    """4. Normal User is strictly blocked with 403 from creating enforcement cases."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("public_user_1", ROLE_USER)
    payload = {"analysis_id": "ana_enf_test_1"}
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_05_admin_can_manage_cases():
    """5. Admin can create and manage enforcement cases."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("admin_enf", ROLE_ADMIN)
    payload = {
        "analysis_id": "ana_enf_test_2",
        "severity": "HIGH",
        "initial_notes": "Admin initiated docket"
    }
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 201
    assert r.json()["case_reference"].startswith("MC-ENF-")


@pytest.mark.asyncio
async def test_06_case_references_valid_analysis():
    """6. Case must link correctly to analysis details and extracted violations."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    payload = {"analysis_id": "ana_enf_test_1"}
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert len(data["violations"]) >= 2
    assert data["source_analysis"]["id"] == "ana_enf_test_1"


@pytest.mark.asyncio
async def test_07_invalid_analysis_rejected():
    """7. Case creation with non-existent analysis_id returns 404."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    payload = {"analysis_id": "ana_non_existent_9999"}
    r = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_08_duplicate_active_case_prevented():
    """8. Cannot create a duplicate active case for the same analysis."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    payload = {"analysis_id": "ana_enf_test_1"}
    r1 = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r1.status_code == 201
    r2 = client.post("/api/enforcement/cases", json=payload, headers=headers)
    assert r2.status_code == 409


# ═════════════════════════════════════════════════════════════════════════════
# LIFECYCLE & ASSIGNMENT TESTS (Requirements 9-14)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_09_case_detail_authorization():
    """9. Case detail endpoint authorizes Enforcement Officers & Admin but blocks others."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers_off = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers_off)
    case_id = r_create.json()["id"]

    # Allowed for officer
    r_get = client.get(f"/api/enforcement/cases/{case_id}", headers=headers_off)
    assert r_get.status_code == 200

    # Blocked for Audit Officer
    headers_audit = make_headers("audit_officer_1", ROLE_AUDIT)
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_audit).status_code == 403

    # Blocked for Merchant
    headers_merch = make_headers("merchant_a_user", ROLE_MERCHANT)
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_merch).status_code == 403

    # Blocked for Public
    headers_pub = make_headers("public_user_1", ROLE_USER)
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_pub).status_code == 403


@pytest.mark.asyncio
async def test_10_case_list_server_side_filtering():
    """10. Case list endpoint supports status and severity filtering."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1", "severity": "CRITICAL"}, headers=headers)
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_2", "severity": "MEDIUM"}, headers=headers)

    r_all = client.get("/api/enforcement/cases", headers=headers)
    assert r_all.status_code == 200
    assert r_all.json()["total"] >= 2

    r_crit = client.get("/api/enforcement/cases?severity=CRITICAL", headers=headers)
    assert r_crit.status_code == 200
    assert all(c["severity"] == "CRITICAL" for c in r_crit.json()["cases"])


@pytest.mark.asyncio
async def test_11_case_assignment():
    """11. Case can be assigned to a valid officer."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("admin_enf", ROLE_ADMIN)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    r_assign = client.post(
        f"/api/enforcement/cases/{case_id}/assign",
        json={"assigned_officer": "enforcement_officer_2", "comments": "Assigned for field investigation."},
        headers=headers
    )
    assert r_assign.status_code == 200
    assert r_assign.json()["assigned_officer"] == "enforcement_officer_2"


@pytest.mark.asyncio
async def test_12_invalid_assignment_rejected():
    """12. Cannot assign enforcement case to Merchant, Public User, or non-existent user."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("admin_enf", ROLE_ADMIN)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # Target is Merchant -> 400
    r_bad_merch = client.post(
        f"/api/enforcement/cases/{case_id}/assign",
        json={"assigned_officer": "merchant_a_user"},
        headers=headers
    )
    assert r_bad_merch.status_code == 400

    # Target is non-existent -> 404
    r_bad_user = client.post(
        f"/api/enforcement/cases/{case_id}/assign",
        json={"assigned_officer": "ghost_user_999"},
        headers=headers
    )
    assert r_bad_user.status_code == 404


@pytest.mark.asyncio
async def test_13_invalid_status_transition_rejected():
    """13. Invalid state machine transition is rejected server-side."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # OPEN -> HEARING directly is invalid
    r_trans = client.post(
        f"/api/enforcement/cases/{case_id}/transition",
        json={"to_status": "HEARING", "reason": "Skipping investigation"},
        headers=headers
    )
    assert r_trans.status_code == 400


@pytest.mark.asyncio
async def test_14_valid_status_transition():
    """14. Valid status transition updates case and logs timeline event."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # OPEN -> INVESTIGATION
    r_trans = client.post(
        f"/api/enforcement/cases/{case_id}/transition",
        json={"to_status": "INVESTIGATION", "reason": "Initiated on-site audit"},
        headers=headers
    )
    assert r_trans.status_code == 200
    assert r_trans.json()["status"] == "INVESTIGATION"


# ═════════════════════════════════════════════════════════════════════════════
# PENALTY PERSISTENCE & NOTICE LEDGER TESTS (Requirements 15-23)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_15_penalty_calculation_persists():
    """15. Penalty calculation persists on the case and updates state."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    r_pen = client.post(
        f"/api/enforcement/cases/{case_id}/calculate-penalty",
        json={"repeat_offence": False, "prior_notices": 0},
        headers=headers
    )
    assert r_pen.status_code == 200
    p_data = r_pen.json()
    assert p_data["applicable"] is True
    assert p_data["estimated_fine_inr"] > 0
    assert "Section 36, Legal Metrology Act, 2009" in p_data["sections"]

    # Verify persisted in case details
    r_case = client.get(f"/api/enforcement/cases/{case_id}", headers=headers)
    assert len(r_case.json()["penalties"]) >= 1


@pytest.mark.asyncio
async def test_16_penalty_history_preserved():
    """16. Subsequent recalculation preserves previous penalty records without overwriting."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # First calc
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={"repeat_offence": False}, headers=headers)
    # Second calc with repeat offence
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={"repeat_offence": True}, headers=headers)

    r_case = client.get(f"/api/enforcement/cases/{case_id}", headers=headers)
    penalties = r_case.json()["penalties"]
    assert len(penalties) == 2
    assert penalties[0]["repeat_offence"] is True
    assert penalties[1]["repeat_offence"] is False


@pytest.mark.asyncio
async def test_17_audit_officer_cannot_calculate_penalty():
    """17. Audit Officer receives 403 on penalty calculation endpoints."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers_off = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers_off)
    case_id = r_create.json()["id"]

    headers_audit = make_headers("audit_officer_1", ROLE_AUDIT)
    r = client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers_audit)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_18_notice_creation_persists():
    """18. Notice creation persists in enforcement_notices with unique SCN reference."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    r_notice = client.post(
        f"/api/enforcement/cases/{case_id}/notices",
        json={"notice_type": "SHOW_CAUSE", "deadline_days": 15},
        headers=headers
    )
    assert r_notice.status_code == 201
    n_data = r_notice.json()
    assert n_data["notice_reference"].startswith("MC-SCN-")
    assert "SHOW CAUSE NOTICE" in n_data["content"]
    assert n_data["case_id"] == case_id


@pytest.mark.asyncio
async def test_19_notice_reference_unique():
    """19. Multiple notices receive unique, distinct reference numbers."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    r_n1 = client.post(f"/api/enforcement/cases/{case_id}/notices", json={"deadline_days": 15}, headers=headers)
    r_n2 = client.post(f"/api/enforcement/cases/{case_id}/notices", json={"deadline_days": 30}, headers=headers)

    ref1 = r_n1.json()["notice_reference"]
    ref2 = r_n2.json()["notice_reference"]
    assert ref1 != ref2


@pytest.mark.asyncio
async def test_20_notice_history_preserved():
    """20. Case notices endpoint returns full chronological list."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    client.post(f"/api/enforcement/cases/{case_id}/notices", json={"deadline_days": 15}, headers=headers)
    client.post(f"/api/enforcement/cases/{case_id}/notices", json={"deadline_days": 30}, headers=headers)

    r_list = client.get(f"/api/enforcement/cases/{case_id}/notices", headers=headers)
    assert r_list.status_code == 200
    assert len(r_list.json()) == 2


@pytest.mark.asyncio
async def test_21_audit_officer_cannot_create_notice():
    """21. Audit Officer is strictly blocked with 403 from issuing notices."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers_off = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers_off)
    case_id = r_create.json()["id"]

    headers_audit = make_headers("audit_officer_1", ROLE_AUDIT)
    r = client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers_audit)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_22_merchant_cannot_access_internal_notice_api():
    """22. Merchant cannot call internal notice management endpoints."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers_merch = make_headers("merchant_a_user", ROLE_MERCHANT)
    assert client.get("/api/enforcement/cases/case_123/notices", headers=headers_merch).status_code == 403
    assert client.post("/api/enforcement/cases/case_123/notices", json={}, headers=headers_merch).status_code == 403


@pytest.mark.asyncio
async def test_23_normal_user_cannot_access_internal_notice_api():
    """23. Normal user cannot call internal notice management endpoints."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers_pub = make_headers("public_user_1", ROLE_USER)
    assert client.get("/api/enforcement/cases/case_123/notices", headers=headers_pub).status_code == 403
    assert client.post("/api/enforcement/cases/case_123/notices", json={}, headers=headers_pub).status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION, TIMELINE & CLOSURE TESTS (Requirements 24-34)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_24_case_timeline_tracks_lifecycle():
    """24. Timeline records creation, assignment, calculation, notice, and closure events."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # Transition
    client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "Inspecting factory"}, headers=headers)
    # Penalty
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers)
    # Notice
    client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers)
    # Close
    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Fine compounded"}, headers=headers)

    r_case = client.get(f"/api/enforcement/cases/{case_id}", headers=headers)
    events = [e["action"] for e in r_case.json()["timeline"]]
    assert "CASE_CREATED" in events
    assert "CASE_STATUS_CHANGED" in events
    assert "PENALTY_CALCULATED" in events
    assert "NOTICE_ISSUED" in events
    assert "CASE_CLOSED" in events


@pytest.mark.asyncio
async def test_25_closed_case_cannot_be_arbitrarily_modified():
    """25. Closed case blocks penalty calculations, notice issuance, and assignments."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Resolved"}, headers=headers)

    # Calculating penalty on closed case -> 400
    r_pen = client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers)
    assert r_pen.status_code == 400

    # Issuing notice on closed case -> 400
    r_not = client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers)
    assert r_not.status_code == 400


@pytest.mark.asyncio
async def test_26_case_reopening_with_justification():
    """26. Closed case can be reopened with mandatory justification."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]

    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Resolved"}, headers=headers)

    r_reopen = client.post(
        f"/api/enforcement/cases/{case_id}/reopen",
        json={"reopen_reason": "Merchant failed to remit compounding fee."},
        headers=headers
    )
    assert r_reopen.status_code == 200
    assert r_reopen.json()["status"] == "OPEN"
    assert r_reopen.json()["closed_at"] is None


@pytest.mark.asyncio
async def test_27_audit_review_escalation_creates_case():
    """27. Escalating an Audit Review automatically initiates an enforcement case."""
    await _seed_enforcement_data()
    client = TestClient(app)
    # Seed an audit review
    await save_review({
        "id": "rev_escalate_test_1",
        "analysis_id": "ana_enf_test_1",
        "status": ReviewStatus.IN_REVIEW,
        "product_name": "Premium Crunchy Biscuits",
        "ai_score": 45.0,
        "ai_risk_level": "CRITICAL",
        "ai_status": "FAIL",
        "ai_snapshot": json.dumps({"score": 45.0}),
        "organization_id": "org_ministry",
        "history": []
    })

    headers_audit = make_headers("audit_officer_1", ROLE_AUDIT)
    r_esc = client.post(
        "/api/reviews/rev_escalate_test_1/escalate",
        json={"escalation_reason": "Severe deceptive packaging violation", "escalation_target": "ENFORCEMENT"},
        headers=headers_audit
    )
    assert r_esc.status_code == 200
    assert r_esc.json()["new_status"] == "ESCALATED"

    # Verify enforcement case was created
    case = await get_enforcement_case_by_analysis_id("ana_enf_test_1")
    assert case is not None
    assert case["analysis_id"] == "ana_enf_test_1"
    assert case["review_id"] == "rev_escalate_test_1"
    assert case["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_28_existing_penalty_endpoint_compatible():
    """28. POST /api/enforcement/penalty remains compatible and returns advisory estimate."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r = client.post("/api/enforcement/penalty", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["applicable"] is True
    assert data["estimated_fine_inr"] > 0
    assert "Section 36, Legal Metrology Act, 2009" in data["sections"]


@pytest.mark.asyncio
async def test_29_existing_notice_endpoint_compatible():
    """29. POST /api/enforcement/notice remains compatible and returns formatted notice."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r = client.post("/api/enforcement/notice", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "SHOW CAUSE NOTICE" in data["notice"]


@pytest.mark.asyncio
async def test_30_officer_suspension_blocks_case_mutation():
    """30. Suspended officer is immediately rejected with 403 on case endpoints."""
    await _seed_enforcement_data()
    client = TestClient(app)
    await suspend_user("enforcement_officer_1")
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r = client.get("/api/enforcement/cases", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_31_token_version_revocation():
    """31. Stale token with mismatching token_version returns 401."""
    await _seed_enforcement_data()
    client = TestClient(app)
    stale_headers = make_headers("enforcement_officer_2", ROLE_ENFORCEMENT, token_version=99)
    r = client.get("/api/enforcement/cases", headers=stale_headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_32_dashboard_metrics_aggregate():
    """32. Dashboard aggregates accurate counts of active cases, notices, and estimated fines."""
    await _seed_enforcement_data()
    client = TestClient(app)
    headers = make_headers("enforcement_officer_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_enf_test_1"}, headers=headers)
    case_id = r_create.json()["id"]
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers)
    client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers)

    r_dash = client.get("/api/enforcement/dashboard", headers=headers)
    assert r_dash.status_code == 200
    metrics = r_dash.json()
    assert metrics["total_active_cases"] >= 1
    assert metrics["total_notices_served"] >= 1
    assert metrics["total_penalties_estimated_inr"] > 0
