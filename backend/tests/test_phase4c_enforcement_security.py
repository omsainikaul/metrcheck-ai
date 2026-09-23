"""
Phase 4C Test Suite 1: Enforcement Security & Role Matrix Audit
Tests strict RBAC, IDOR protection, State Machine abuse prevention,
Closed-Case immutability, Reopening security, Assignment validation,
Penalty/Notice persistence, and Token Revocation.
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
    save_enforcement_case,
    get_enforcement_case,
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

from models.enforcement_schemas import CaseStatus, CaseSeverity, NoticeType


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Running on prod DB!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Running on prod upload dir!"


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


async def _seed_security_data():
    await init_db()
    db = await get_db()
    try:
        await db.execute("DELETE FROM enforcement_notices")
        await db.execute("DELETE FROM penalty_calculations")
        await db.execute("DELETE FROM enforcement_cases")
        await db.execute("DELETE FROM officer_reviews")
        await db.execute("UPDATE users SET status = 'ACTIVE', token_version = 1 WHERE username LIKE 'sec_%'")
        await db.commit()
    finally:
        await db.close()

    # Orgs
    await create_organization("org_sec_reg_a", "State Enforcement Authority Alpha", org_type="REGULATOR", jurisdiction="State A")
    await create_organization("org_sec_reg_b", "State Enforcement Authority Beta", org_type="REGULATOR", jurisdiction="State B")
    await create_organization("org_sec_merch", "Security Target Merchant Ltd", org_type="MERCHANT", jurisdiction="National")

    # Users across all 5 roles
    await _create_test_user("sec_admin", ROLE_ADMIN, "")
    await _create_test_user("sec_enf_a1", ROLE_ENFORCEMENT, "org_sec_reg_a", state="State A", district="North")
    await _create_test_user("sec_enf_a2", ROLE_ENFORCEMENT, "org_sec_reg_a", state="State A", district="South")
    await _create_test_user("sec_enf_b1", ROLE_ENFORCEMENT, "org_sec_reg_b", state="State B", district="Central")
    await _create_test_user("sec_audit_1", ROLE_AUDIT, "org_sec_reg_a")
    await _create_test_user("sec_merchant_1", ROLE_MERCHANT, "org_sec_merch")
    await _create_test_user("sec_public_1", ROLE_USER, "")

    # Analyses
    await save_analysis({
        "id": "ana_sec_a_1",
        "product_name": "Crunchy Protein Bar 50g",
        "image_filename": "bar.jpg",
        "owner_user_id": "sec_enf_a1",
        "organization_id": "org_sec_reg_a",
        "score": 50.0,
        "status": "FAIL",
        "created_at": "2026-03-01T10:00:00Z",
        "compliance_result": json.dumps({
            "score": 50.0,
            "status": "FAIL",
            "checks": [
                {"field": "mrp", "field_label": "Maximum Retail Price", "status": "FAIL", "required": True, "reason": "Missing declaration", "rule_id": "Rule 6(1)(e)"}
            ]
        })
    })

    await save_analysis({
        "id": "ana_sec_b_1",
        "product_name": "Herbal Tea Extract 100g",
        "image_filename": "tea.jpg",
        "owner_user_id": "sec_enf_b1",
        "organization_id": "org_sec_reg_b",
        "score": 40.0,
        "status": "FAIL",
        "created_at": "2026-03-01T11:00:00Z",
        "compliance_result": json.dumps({
            "score": 40.0,
            "status": "FAIL",
            "checks": [
                {"field": "net_quantity", "field_label": "Net Quantity", "status": "FAIL", "required": True, "reason": "Non-standard unit", "rule_id": "Rule 11"}
            ]
        })
    })


# ═════════════════════════════════════════════════════════════════════════════
# 1. COMPLETE ROLE MATRIX AUDIT (Requirements 4 & 5)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_role_matrix_dashboard_access():
    """Verify dashboard access across all 5 roles."""
    await _seed_security_data()
    client = TestClient(app)

    # Allowed: ADMIN & ENFORCEMENT
    assert client.get("/api/enforcement/dashboard", headers=make_headers("sec_admin", ROLE_ADMIN)).status_code == 200
    assert client.get("/api/enforcement/dashboard", headers=make_headers("sec_enf_a1", ROLE_ENFORCEMENT)).status_code == 200

    # Denied: AUDIT, MERCHANT, USER
    assert client.get("/api/enforcement/dashboard", headers=make_headers("sec_audit_1", ROLE_AUDIT)).status_code == 403
    assert client.get("/api/enforcement/dashboard", headers=make_headers("sec_merchant_1", ROLE_MERCHANT)).status_code == 403
    assert client.get("/api/enforcement/dashboard", headers=make_headers("sec_public_1", ROLE_USER)).status_code == 403


@pytest.mark.asyncio
async def test_02_role_matrix_case_creation():
    """Verify case creation permissions across all 5 roles."""
    await _seed_security_data()
    client = TestClient(app)
    body = {"analysis_id": "ana_sec_a_1"}

    # Audit, Merchant, User must be rejected with 403
    assert client.post("/api/enforcement/cases", json=body, headers=make_headers("sec_audit_1", ROLE_AUDIT)).status_code == 403
    assert client.post("/api/enforcement/cases", json=body, headers=make_headers("sec_merchant_1", ROLE_MERCHANT)).status_code == 403
    assert client.post("/api/enforcement/cases", json=body, headers=make_headers("sec_public_1", ROLE_USER)).status_code == 403

    # Enforcement Officer in authorized org can create
    r_enf = client.post("/api/enforcement/cases", json=body, headers=make_headers("sec_enf_a1", ROLE_ENFORCEMENT))
    assert r_enf.status_code == 201


@pytest.mark.asyncio
async def test_03_role_matrix_case_actions():
    """Verify assignment, transitions, penalties, and notices are blocked for unauthorized roles."""
    await _seed_security_data()
    client = TestClient(app)

    # Create active case by Enforcement Officer
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=make_headers("sec_enf_a1", ROLE_ENFORCEMENT))
    case_id = r_create.json()["id"]

    for role, username in [
        (ROLE_AUDIT, "sec_audit_1"),
        (ROLE_MERCHANT, "sec_merchant_1"),
        (ROLE_USER, "sec_public_1"),
    ]:
        headers = make_headers(username, role)
        # GET case detail
        assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers).status_code == 403
        # POST assign
        assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "sec_enf_a1"}, headers=headers).status_code == 403
        # POST transition
        assert client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "Audit"}, headers=headers).status_code == 403
        # POST calculate penalty
        assert client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers).status_code == 403
        # POST issue notice
        assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers).status_code == 403
        # GET notices
        assert client.get(f"/api/enforcement/cases/{case_id}/notices", headers=headers).status_code == 403
        # POST close
        assert client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "compounded"}, headers=headers).status_code == 403
        # POST reopen
        assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "new proof"}, headers=headers).status_code == 403


# ═════════════════════════════════════════════════════════════════════════════
# 2. CASE IDOR / OBJECT AUTHORIZATION FUZZING (Requirement 7)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_04_cross_tenant_case_idor():
    """Enforcement officer in Org A cannot access or mutate a case in Org B."""
    await _seed_security_data()
    client = TestClient(app)

    # Org B officer creates a case for Org B analysis
    r_b = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_b_1"}, headers=make_headers("sec_enf_b1", ROLE_ENFORCEMENT))
    assert r_b.status_code == 201
    case_b_id = r_b.json()["id"]

    # Org A officer attempts access
    headers_a = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    assert client.get(f"/api/enforcement/cases/{case_b_id}", headers=headers_a).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_b_id}/assign", json={"assigned_officer": "sec_enf_a1"}, headers=headers_a).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_b_id}/transition", json={"to_status": "INVESTIGATION", "reason": "probe"}, headers=headers_a).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_b_id}/calculate-penalty", json={}, headers=headers_a).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_b_id}/notices", json={}, headers=headers_a).status_code == 403
    assert client.get(f"/api/enforcement/cases/{case_b_id}/notices", headers=headers_a).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_b_id}/close", json={"closure_reason": "done"}, headers=headers_a).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_b_id}/reopen", json={"reopen_reason": "done"}, headers=headers_a).status_code == 403


@pytest.mark.asyncio
async def test_05_case_id_fuzzing_and_traversal():
    """Case endpoints reject malformed, path traversal, and SQL-like case IDs with 404/400."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    malicious_ids = [
        "case-../../etc/passwd",
        "case-1' OR '1'='1",
        "case-<script>alert(1)</script>",
        "case-non-existent-99999",
        "CASE_RANDOM_UUID_1234567890",
        "case-null",
        "case-" + "A" * 500
    ]

    for bad_id in malicious_ids:
        r_get = client.get(f"/api/enforcement/cases/{bad_id}", headers=headers)
        assert r_get.status_code in (404, 400, 422)


# ═════════════════════════════════════════════════════════════════════════════
# 3. ANALYSIS -> CASE RELATIONSHIP VALIDATION (Requirement 8)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_06_analysis_cross_tenant_creation_idor():
    """Officer in Org A cannot create a case targeting an analysis in Org B."""
    await _seed_security_data()
    client = TestClient(app)

    # sec_enf_a1 tries to create case referencing ana_sec_b_1 (owned by Org B)
    headers_a = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)
    r = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_b_1"}, headers=headers_a)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_07_forged_merchant_org_derivation():
    """Backend ignores client-forged merchant_organization_id and uses authoritative DB record."""
    await _seed_security_data()
    client = TestClient(app)
    headers_a = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    # Pass forged merchant_organization_id
    payload = {
        "analysis_id": "ana_sec_a_1",
        "merchant_organization_id": "org_forged_evil_corp"
    }
    r = client.post("/api/enforcement/cases", json=payload, headers=headers_a)
    assert r.status_code == 201
    data = r.json()
    # Merchant organization must match analysis authoritative org or be derived safely
    assert data["merchant_organization_id"] != "org_forged_evil_corp"


# ═════════════════════════════════════════════════════════════════════════════
# 4. STATE MACHINE INTEGRITY & ILLEGAL TRANSITIONS (Requirement 10)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_08_illegal_state_machine_transitions():
    """Reject all illegal state transitions according to lifecycle rules."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # In OPEN status: illegal to jump straight to HEARING, RESOLVED, or NOTICE_ISSUED
    for invalid_status in ["HEARING", "RESOLVED", "NOTICE_ISSUED", "GARBAGE_STATE"]:
        r_bad = client.post(
            f"/api/enforcement/cases/{case_id}/transition",
            json={"to_status": invalid_status, "reason": "bypass test"},
            headers=headers
        )
        assert r_bad.status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
# 5. CLOSED CASE INTEGRITY & REOPEN SECURITY (Requirements 11 & 12)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_09_closed_case_mutation_locks():
    """Closed case strictly rejects assignment, transitions, penalties, notices, and direct mutation."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # Close case
    r_close = client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Full compounding fee settled"}, headers=headers)
    assert r_close.status_code == 200

    # All mutations must be rejected with 400
    assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "sec_enf_a2"}, headers=headers).status_code == 400
    assert client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers).status_code == 400
    assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers).status_code == 400
    assert client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "probe"}, headers=headers).status_code == 400


@pytest.mark.asyncio
async def test_10_reopen_justification_enforcement():
    """Reopening a closed case requires non-empty, non-whitespace justification."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]
    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Settled"}, headers=headers)

    # Empty / whitespace-only justification -> rejected
    assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": ""}, headers=headers).status_code in (400, 422)
    assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "   "}, headers=headers).status_code in (400, 422)

    # Valid justification -> succeeds and creates timeline event
    r_reopen = client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "Dishonored compounding instrument"}, headers=headers)
    assert r_reopen.status_code == 200
    case_after = r_reopen.json()
    assert case_after["status"] == "OPEN"
    reopen_events = [e for e in case_after["timeline"] if e["action"] == "CASE_REOPENED"]
    assert len(reopen_events) == 1
    assert "Dishonored compounding instrument" in reopen_events[0]["details"]


# ═════════════════════════════════════════════════════════════════════════════
# 6. ASSIGNMENT VALIDATION & DISQUALIFIED ACTORS (Requirement 13)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_11_assignment_disqualification():
    """Cannot assign enforcement cases to Audit officers, Merchants, Normal users, or suspended officers."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # Target: Audit Officer -> 400
    assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "sec_audit_1"}, headers=headers).status_code == 400

    # Target: Merchant -> 400
    assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "sec_merchant_1"}, headers=headers).status_code == 400

    # Target: Normal User -> 400
    assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "sec_public_1"}, headers=headers).status_code == 400

    # Target: Suspended Enforcement Officer -> 400
    await suspend_user("sec_enf_a2")
    assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "sec_enf_a2"}, headers=headers).status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
# 7. PENALTY & NOTICE LEDGER IMMUTABILITY (Requirements 14-16)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_12_penalty_history_preservation():
    """Penalty recalculations create distinct history entries without overwriting previous calculations."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # First calc
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={"repeat_offence": False, "prior_notices": 0}, headers=headers)
    # Second calc (subsequent inspection)
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={"repeat_offence": True, "prior_notices": 1}, headers=headers)

    r_case = client.get(f"/api/enforcement/cases/{case_id}", headers=headers)
    penalties = r_case.json()["penalties"]
    assert len(penalties) == 2
    assert penalties[0]["repeat_offence"] is True
    assert penalties[1]["repeat_offence"] is False


@pytest.mark.asyncio
async def test_13_notice_ledger_uniqueness_and_immutability():
    """Notices receive unique references and cannot be deleted or mutated via API."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    r_n1 = client.post(f"/api/enforcement/cases/{case_id}/notices", json={"notice_type": "SHOW_CAUSE"}, headers=headers)
    r_n2 = client.post(f"/api/enforcement/cases/{case_id}/notices", json={"notice_type": "COMPOUNDING_SUMMONS"}, headers=headers)

    n1 = r_n1.json()
    n2 = r_n2.json()

    assert n1["notice_reference"].startswith("MC-SCN-")
    assert n2["notice_reference"].startswith("MC-CMP-")
    assert n1["notice_reference"] != n2["notice_reference"]

    # Verify no update/delete endpoint exists that mutates archived notice
    assert client.delete(f"/api/enforcement/notices/{n1['id']}", headers=headers).status_code in (404, 405)
    assert client.put(f"/api/enforcement/notices/{n1['id']}", json={"content": "tampered"}, headers=headers).status_code in (404, 405)


# ═════════════════════════════════════════════════════════════════════════════
# 8. TOKEN REVOCATION & SUSPENDED OFFICER ISOLATION (Requirements 19 & 20)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_14_token_version_immediate_revocation():
    """Incrementing user token_version immediately invalidates active JWT across all enforcement routes."""
    await _seed_security_data()
    client = TestClient(app)

    # Stale token with mismatching token_version
    stale_headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT, token_version=42)

    assert client.get("/api/enforcement/dashboard", headers=stale_headers).status_code == 401
    assert client.get("/api/enforcement/cases", headers=stale_headers).status_code == 401
    assert client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=stale_headers).status_code == 401


@pytest.mark.asyncio
async def test_15_suspended_officer_immediate_block():
    """Suspended officer is immediately rejected with 403 across all case operations."""
    await _seed_security_data()
    client = TestClient(app)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=make_headers("sec_enf_a1", ROLE_ENFORCEMENT))
    case_id = r_create.json()["id"]

    # Suspend officer
    await suspend_user("sec_enf_a1")
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    assert client.get("/api/enforcement/dashboard", headers=headers).status_code == 403
    assert client.get("/api/enforcement/cases", headers=headers).status_code == 403
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "x"}, headers=headers).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_16_compat_endpoints_role_matrix():
    """Verify legacy /penalty and /notice compatibility endpoints across all 5 roles."""
    await _seed_security_data()
    client = TestClient(app)
    req_pen = {"analysis_id": "ana_sec_a_1"}
    req_not = {"analysis_id": "ana_sec_a_1"}

    # Allowed: Admin & Enforcement in Org A
    assert client.post("/api/enforcement/penalty", json=req_pen, headers=make_headers("sec_admin", ROLE_ADMIN)).status_code == 200
    assert client.post("/api/enforcement/notice", json=req_not, headers=make_headers("sec_admin", ROLE_ADMIN)).status_code == 200
    assert client.post("/api/enforcement/penalty", json=req_pen, headers=make_headers("sec_enf_a1", ROLE_ENFORCEMENT)).status_code == 200
    assert client.post("/api/enforcement/notice", json=req_not, headers=make_headers("sec_enf_a1", ROLE_ENFORCEMENT)).status_code == 200

    # Denied: Audit, Merchant, Normal User (403)
    for role, username in [(ROLE_AUDIT, "sec_audit_1"), (ROLE_MERCHANT, "sec_merchant_1"), (ROLE_USER, "sec_public_1")]:
        headers = make_headers(username, role)
        assert client.post("/api/enforcement/penalty", json=req_pen, headers=headers).status_code == 403
        assert client.post("/api/enforcement/notice", json=req_not, headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_17_cross_tenant_notice_detail_idor():
    """Officer A cannot read notice details for a notice issued under Org B's case."""
    await _seed_security_data()
    client = TestClient(app)

    # Org B creates case and notice
    headers_b = make_headers("sec_enf_b1", ROLE_ENFORCEMENT)
    r_case_b = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_b_1"}, headers=headers_b)
    case_b_id = r_case_b.json()["id"]
    r_not_b = client.post(f"/api/enforcement/cases/{case_b_id}/notices", json={"notice_type": "SHOW_CAUSE"}, headers=headers_b)
    notice_b_id = r_not_b.json()["id"]

    # Org A attempts to inspect notice B detail
    headers_a = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)
    assert client.get(f"/api/enforcement/notices/{notice_b_id}", headers=headers_a).status_code == 403

    # Admin retains global access
    headers_admin = make_headers("sec_admin", ROLE_ADMIN)
    assert client.get(f"/api/enforcement/notices/{notice_b_id}", headers=headers_admin).status_code == 200


@pytest.mark.asyncio
async def test_18_nonexistent_case_and_analysis_penalty_fails():
    """Penalty endpoint returns 404 when case or analysis does not exist."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    assert client.post("/api/enforcement/cases/case_ghost_999/calculate-penalty", json={}, headers=headers).status_code == 404
    assert client.post("/api/enforcement/penalty", json={"analysis_id": "ana_ghost_999"}, headers=headers).status_code == 404


@pytest.mark.asyncio
async def test_19_nonexistent_case_notice_creation_fails():
    """Notice creation returns 404 when target case does not exist."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)
    assert client.post("/api/enforcement/cases/case_ghost_999/notices", json={}, headers=headers).status_code == 404


@pytest.mark.asyncio
async def test_20_assign_to_nonexistent_officer_fails():
    """Attempting to assign a case to a non-existent officer returns 404."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    assert client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "ghost_officer_404"}, headers=headers).status_code == 404


@pytest.mark.asyncio
async def test_21_case_reopen_only_permitted_from_closed_or_resolved():
    """Attempting to reopen an active OPEN or INVESTIGATION case returns 400."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # In OPEN state -> 400
    assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "premature"}, headers=headers).status_code == 400

    # In INVESTIGATION state -> 400
    client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "probe"}, headers=headers)
    assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "premature"}, headers=headers).status_code == 400


@pytest.mark.asyncio
async def test_22_case_close_already_closed_case_fails():
    """Closing an already closed case returns 400."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Settled"}, headers=headers)
    # Second close attempt -> 400
    assert client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Settled again"}, headers=headers).status_code == 400


@pytest.mark.asyncio
async def test_23_custom_notice_content_persists():
    """Custom notice body provided by officer is saved verbatim into notice ledger."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]

    custom_text = "SPECIAL STATUTORY WARNING: Immediate seizure of non-compliant stock scheduled under Rule 32."
    r_not = client.post(
        f"/api/enforcement/cases/{case_id}/notices",
        json={"notice_type": "SEIZURE_ORDER", "custom_content": custom_text},
        headers=headers
    )
    assert r_not.status_code == 201
    assert r_not.json()["content"] == custom_text


@pytest.mark.asyncio
async def test_24_suspended_officer_blocked_on_notice_endpoints():
    """Suspended officer is blocked on notice retrieval endpoints."""
    await _seed_security_data()
    client = TestClient(app)
    headers = make_headers("sec_enf_a1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_a_1"}, headers=headers)
    case_id = r_create.json()["id"]
    r_not = client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers)
    not_id = r_not.json()["id"]

    await suspend_user("sec_enf_a1")
    assert client.get(f"/api/enforcement/cases/{case_id}/notices", headers=headers).status_code == 403
    assert client.get(f"/api/enforcement/notices/{not_id}", headers=headers).status_code == 403


@pytest.mark.asyncio
async def test_25_admin_global_case_oversight():
    """Administrator retains statutory global oversight and can execute all actions across all orgs."""
    await _seed_security_data()
    client = TestClient(app)
    headers_b = make_headers("sec_enf_b1", ROLE_ENFORCEMENT)
    headers_admin = make_headers("sec_admin", ROLE_ADMIN)

    # Org B creates case
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_sec_b_1"}, headers=headers_b)
    case_id = r_create.json()["id"]

    # Admin reads detail, calculates penalty, issues notice, closes and reopens case
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_admin).status_code == 200
    assert client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers_admin).status_code == 200
    assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers_admin).status_code == 201
    assert client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Admin closed case"}, headers=headers_admin).status_code == 200
    assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "Admin reopened for audit"}, headers=headers_admin).status_code == 200
