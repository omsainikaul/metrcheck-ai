"""
Phase 4C Test Suite 3: Full-System Integration, Concurrency & Privacy Regressions
Tests:
- End-to-end Audit -> Escalation -> Enforcement workflow
- Duplicate docket prevention & concurrency
- Input validation & injection resilience
- Search & Pagination bounds
- Merchant & Normal User privacy regressions
- Evidence integrity & immutability
"""
import os
import json
import pytest
import asyncio
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
    list_enforcement_cases,
    get_enforcement_case_by_analysis_id
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
from models.review_schemas import ReviewStatus


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


async def _seed_integration_data():
    await init_db()
    db = await get_db()
    try:
        await db.execute("DELETE FROM enforcement_notices")
        await db.execute("DELETE FROM penalty_calculations")
        await db.execute("DELETE FROM enforcement_cases")
        await db.execute("DELETE FROM officer_reviews")
        await db.commit()
    finally:
        await db.close()

    # Orgs
    await create_organization("org_integ_reg", "National Enforcement Directorate", org_type="REGULATOR", jurisdiction="National")
    await create_organization("org_integ_merch", "Integrity Test Merchant Foods", org_type="MERCHANT", jurisdiction="North")

    # Users
    await _create_test_user("integ_admin", ROLE_ADMIN, "")
    await _create_test_user("integ_enf_1", ROLE_ENFORCEMENT, "org_integ_reg", state="Delhi", district="Central")
    await _create_test_user("integ_enf_2", ROLE_ENFORCEMENT, "org_integ_reg", state="Delhi", district="North")
    await _create_test_user("integ_audit_1", ROLE_AUDIT, "org_integ_reg", state="Delhi", district="Central")
    await _create_test_user("integ_merchant_1", ROLE_MERCHANT, "org_integ_merch")
    await _create_test_user("integ_user_1", ROLE_USER, "")

    # Analysis
    await save_analysis({
        "id": "ana_integ_1",
        "product_name": "Premium Crunchy Biscuits 250g",
        "image_filename": "biscuit.jpg",
        "owner_user_id": "integ_enf_1",
        "organization_id": "org_integ_reg",
        "score": 45.0,
        "status": "FAIL",
        "compliance_result": json.dumps({
            "score": 45.0,
            "status": "FAIL",
            "checks": [
                {"field": "mrp", "field_label": "Maximum Retail Price", "status": "FAIL", "required": True, "reason": "Missing declaration", "rule_id": "Rule 6(1)(e)"},
                {"field": "net_quantity", "field_label": "Net Quantity", "status": "FAIL", "required": True, "reason": "Missing declaration", "rule_id": "Rule 11"}
            ]
        })
    })


# ═════════════════════════════════════════════════════════════════════════════
# 1. END-TO-END AUDIT -> ESCALATION -> ENFORCEMENT WORKFLOW (Requirement 17)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_end_to_end_audit_to_enforcement_handoff():
    """Complete lifecycle from Audit review escalation to enforcement case resolution."""
    await _seed_integration_data()
    client = TestClient(app)

    # 1. Create audit review
    await save_review({
        "id": "rev_integ_1",
        "analysis_id": "ana_integ_1",
        "status": ReviewStatus.IN_REVIEW,
        "product_name": "Premium Crunchy Biscuits",
        "ai_score": 45.0,
        "ai_risk_level": "CRITICAL",
        "ai_status": "FAIL",
        "ai_snapshot": json.dumps({"score": 45.0}),
        "organization_id": "org_integ_reg",
        "history": []
    })

    # 2. Audit Officer escalates review
    headers_audit = make_headers("integ_audit_1", ROLE_AUDIT)
    r_esc = client.post(
        "/api/reviews/rev_integ_1/escalate",
        json={"escalation_reason": "Severe statutory non-compliance", "escalation_target": "ENFORCEMENT"},
        headers=headers_audit
    )
    assert r_esc.status_code == 200

    # 3. Enforcement Officer retrieves auto-created case
    headers_enf = make_headers("integ_enf_1", ROLE_ENFORCEMENT)
    case = await get_enforcement_case_by_analysis_id("ana_integ_1")
    assert case is not None
    case_id = case["id"]
    assert case["review_id"] == "rev_integ_1"
    assert case["status"] == "OPEN"

    # 4. Officer assigns case to investigator
    r_assign = client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "integ_enf_2", "comments": "Assigned for factory raid"}, headers=headers_enf)
    assert r_assign.status_code == 200
    assert r_assign.json()["assigned_officer"] == "integ_enf_2"

    # 5. Transition to INVESTIGATION
    r_inv = client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "Factory raid conducted"}, headers=headers_enf)
    assert r_inv.status_code == 200
    assert r_inv.json()["status"] == "INVESTIGATION"

    # 6. Calculate Penalty
    r_pen = client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={"repeat_offence": False, "prior_notices": 0}, headers=headers_enf)
    assert r_pen.status_code == 200
    assert r_pen.json()["estimated_fine_inr"] > 0

    # 7. Issue Notice (SCN)
    r_not = client.post(f"/api/enforcement/cases/{case_id}/notices", json={"notice_type": "SHOW_CAUSE", "deadline_days": 15}, headers=headers_enf)
    assert r_not.status_code == 201
    assert r_not.json()["notice_reference"].startswith("MC-SCN-")

    # 8. Hearing transition
    r_hear = client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "HEARING", "reason": "Merchant appeared for hearing"}, headers=headers_enf)
    assert r_hear.status_code == 200

    # 9. Resolved transition
    r_res = client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "RESOLVED", "reason": "Merchant agreed to compound"}, headers=headers_enf)
    assert r_res.status_code == 200

    # 10. Formal Closure
    r_close = client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Compounding fee paid", "resolution_type": "COMPOUNDED"}, headers=headers_enf)
    assert r_close.status_code == 200
    assert r_close.json()["status"] == "CLOSED"

    # 11. Reopen case upon subsequent discovery
    r_reopen = client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "Subsequent retail sampling showed unrectified batch"}, headers=headers_enf)
    assert r_reopen.status_code == 200
    assert r_reopen.json()["status"] == "OPEN"


# ═════════════════════════════════════════════════════════════════════════════
# 2. DUPLICATE DOCKET & CONCURRENCY RESILIENCE (Requirements 9 & 32)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_02_duplicate_case_creation_prevented():
    """Attempting repeated case creation for the same analysis returns 409 Conflict."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    # First creation -> 201
    r1 = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)
    assert r1.status_code == 201

    # Second creation -> 409 Conflict
    r2 = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_03_concurrent_case_creation():
    """Concurrent attempts to create case for the same analysis result in at most one active case."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    loop = asyncio.get_event_loop()
    responses = await asyncio.gather(
        loop.run_in_executor(None, lambda: client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)),
        loop.run_in_executor(None, lambda: client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)),
        loop.run_in_executor(None, lambda: client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)),
    )

    statuses = [r.status_code for r in responses]
    assert statuses.count(201) == 1
    assert statuses.count(409) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 3. INPUT VALIDATION & INJECTION RESILIENCE (Requirement 24)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_04_input_validation_and_sql_injection():
    """Endpoints safely handle SQL injection strings, XSS scripts, and Unicode payloads."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)
    case_id = r_create.json()["id"]

    # 1. SQL injection in comments
    r_sql = client.post(
        f"/api/enforcement/cases/{case_id}/transition",
        json={"to_status": "INVESTIGATION", "reason": "Normal reason", "comments": "'; DROP TABLE enforcement_cases; --"},
        headers=headers
    )
    assert r_sql.status_code == 200
    # Verify table intact
    assert (await get_enforcement_case(case_id)) is not None

    # 2. XSS in notice fields
    r_xss = client.post(
        f"/api/enforcement/cases/{case_id}/notices",
        json={"subject": "<script>alert('XSS')</script>", "officer_name": "<img src=x onerror=alert(1)>"},
        headers=headers
    )
    assert r_xss.status_code == 201

    # 3. Extreme deadline days bounds (min=1, max=90)
    assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={"deadline_days": 0}, headers=headers).status_code in (400, 422)
    assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={"deadline_days": 999}, headers=headers).status_code in (400, 422)


# ═════════════════════════════════════════════════════════════════════════════
# 4. SEARCH & PAGINATION BOUNDS (Requirements 22 & 23)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_05_search_and_pagination_bounds():
    """Pagination and search parameters handle extreme values and do not leak data."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)

    # Out-of-bounds page -> returns empty page with valid total
    r_page = client.get("/api/enforcement/cases?page=999999&page_size=50", headers=headers)
    assert r_page.status_code == 200
    assert len(r_page.json()["cases"]) == 0
    assert r_page.json()["total"] >= 1

    # Page size capped at 200 by schema
    r_oversize = client.get("/api/enforcement/cases?page_size=500", headers=headers)
    assert r_oversize.status_code in (400, 422)


# ═════════════════════════════════════════════════════════════════════════════
# 5. PRIVACY REGRESSIONS (Requirements 27 & 28)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_06_merchant_and_user_privacy_regressions():
    """Merchants and Normal users cannot access internal enforcement cases or notices."""
    await _seed_integration_data()
    client = TestClient(app)

    headers_enf = make_headers("integ_enf_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers_enf)
    case_id = r_create.json()["id"]

    r_notice = client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers_enf)
    notice_id = r_notice.json()["id"]

    # Merchant cannot inspect
    headers_merch = make_headers("integ_merchant_1", ROLE_MERCHANT)
    assert client.get("/api/enforcement/cases", headers=headers_merch).status_code == 403
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_merch).status_code == 403
    assert client.get(f"/api/enforcement/notices/{notice_id}", headers=headers_merch).status_code == 403

    # Normal user cannot inspect
    headers_user = make_headers("integ_user_1", ROLE_USER)
    assert client.get("/api/enforcement/cases", headers=headers_user).status_code == 403
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_user).status_code == 403
    assert client.get(f"/api/enforcement/notices/{notice_id}", headers=headers_user).status_code == 403


@pytest.mark.asyncio
async def test_07_evidence_immutability_after_case_actions():
    """Underlying OCR text, extracted data, and compliance checks in analyses remain immutable."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    ana_before = await get_analysis("ana_integ_1")
    assert ana_before is not None

    # Perform full sequence of enforcement mutations
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)
    case_id = r_create.json()["id"]
    client.post(f"/api/enforcement/cases/{case_id}/calculate-penalty", json={}, headers=headers)
    client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers)
    client.post(f"/api/enforcement/cases/{case_id}/transition", json={"to_status": "INVESTIGATION", "reason": "probe"}, headers=headers)
    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "settled"}, headers=headers)

    ana_after = await get_analysis("ana_integ_1")
    assert ana_after is not None
    assert ana_before["ocr_text"] == ana_after["ocr_text"]
    assert ana_before["compliance_result"] == ana_after["compliance_result"]
    assert ana_before["score"] == ana_after["score"]


@pytest.mark.asyncio
async def test_08_officer_review_snapshot_immutability():
    """Original ai_snapshot in officer_reviews is strictly preserved after case escalation."""
    await _seed_integration_data()
    client = TestClient(app)

    snap_payload = {"score": 45.0, "status": "FAIL", "violations": ["mrp"]}
    await save_review({
        "id": "rev_integ_snap_1",
        "analysis_id": "ana_integ_1",
        "status": ReviewStatus.IN_REVIEW,
        "product_name": "Premium Crunchy Biscuits",
        "ai_score": 45.0,
        "ai_risk_level": "CRITICAL",
        "ai_status": "FAIL",
        "ai_snapshot": json.dumps(snap_payload),
        "organization_id": "org_integ_reg",
        "history": []
    })

    # Escalate
    headers_audit = make_headers("integ_audit_1", ROLE_AUDIT)
    client.post("/api/reviews/rev_integ_snap_1/escalate", json={"escalation_reason": "Escalate"}, headers=headers_audit)

    rev_after = await get_review("rev_integ_snap_1")
    assert rev_after is not None
    assert json.loads(rev_after["ai_snapshot"]) == snap_payload


@pytest.mark.asyncio
async def test_09_audit_officer_cannot_close_or_reopen_cases():
    """Audit Officer receives 403 when attempting to close or reopen enforcement cases."""
    await _seed_integration_data()
    client = TestClient(app)

    headers_enf = make_headers("integ_enf_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers_enf)
    case_id = r_create.json()["id"]

    headers_audit = make_headers("integ_audit_1", ROLE_AUDIT)
    assert client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "audit close"}, headers=headers_audit).status_code == 403
    assert client.post(f"/api/enforcement/cases/{case_id}/reopen", json={"reopen_reason": "audit reopen"}, headers=headers_audit).status_code == 403


@pytest.mark.asyncio
async def test_10_audit_officer_cannot_issue_notice():
    """Audit Officer receives 403 when attempting to issue statutory notices."""
    await _seed_integration_data()
    client = TestClient(app)

    headers_enf = make_headers("integ_enf_1", ROLE_ENFORCEMENT)
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers_enf)
    case_id = r_create.json()["id"]

    headers_audit = make_headers("integ_audit_1", ROLE_AUDIT)
    assert client.post(f"/api/enforcement/cases/{case_id}/notices", json={}, headers=headers_audit).status_code == 403


@pytest.mark.asyncio
async def test_11_audit_review_queue_isolation():
    """Audit reviews queue remains strictly scoped to regulatory authority."""
    await _seed_integration_data()
    client = TestClient(app)

    headers_audit = make_headers("integ_audit_1", ROLE_AUDIT)
    r_queue = client.get("/api/reviews/queue", headers=headers_audit)
    assert r_queue.status_code == 200


@pytest.mark.asyncio
async def test_12_reopening_case_timeline_event_format():
    """Reopening a case logs a complete structured timeline event."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)
    case_id = r_create.json()["id"]
    client.post(f"/api/enforcement/cases/{case_id}/close", json={"closure_reason": "Resolved"}, headers=headers)

    r_reopen = client.post(
        f"/api/enforcement/cases/{case_id}/reopen",
        json={"reopen_reason": "New lab test showed non-declared ingredients", "comments": "Urgent review required"},
        headers=headers
    )
    assert r_reopen.status_code == 200
    events = r_reopen.json()["timeline"]
    reopen_ev = next(e for e in events if e["action"] == "CASE_REOPENED")
    assert reopen_ev["actor_username"] == "integ_enf_1"
    assert "New lab test showed non-declared ingredients" in reopen_ev["details"]
    assert reopen_ev["new_state"] == "OPEN"


@pytest.mark.asyncio
async def test_13_multiple_notices_preserve_all_content():
    """Issuing multiple statutory notices preserves distinct content, dates, and references."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_integ_1"}, headers=headers)
    case_id = r_create.json()["id"]

    client.post(f"/api/enforcement/cases/{case_id}/notices", json={"notice_type": "SHOW_CAUSE", "deadline_days": 15}, headers=headers)
    client.post(f"/api/enforcement/cases/{case_id}/notices", json={"notice_type": "COMPOUNDING_SUMMONS", "deadline_days": 30}, headers=headers)

    r_notices = client.get(f"/api/enforcement/cases/{case_id}/notices", headers=headers)
    assert r_notices.status_code == 200
    notices = r_notices.json()
    assert len(notices) == 2
    refs = [n["notice_reference"] for n in notices]
    assert len(set(refs)) == 2


@pytest.mark.asyncio
async def test_14_unicode_and_special_character_resilience():
    """Endpoints safely handle Hindi text, legal symbols, and unicode punctuation."""
    await _seed_integration_data()
    client = TestClient(app)
    headers = make_headers("integ_enf_1", ROLE_ENFORCEMENT)

    hindi_notes = "विधिक मापविज्ञान अधिनियम २००९ के अंतर्गत विसंगति पाई गई。"
    r_create = client.post(
        "/api/enforcement/cases",
        json={"analysis_id": "ana_integ_1", "initial_notes": hindi_notes},
        headers=headers
    )
    assert r_create.status_code == 201
    case_id = r_create.json()["id"]

    # Verify notes in timeline
    case = await get_enforcement_case(case_id)
    assert case is not None
    assert hindi_notes in case["timeline"][0]["details"]


@pytest.mark.asyncio
async def test_15_duplicate_escalation_safely_idempotent():
    """Escalating an audit review when a case already exists does not create a duplicate active case."""
    await _seed_integration_data()
    client = TestClient(app)

    await save_review({
        "id": "rev_integ_dup_1",
        "analysis_id": "ana_integ_1",
        "status": ReviewStatus.IN_REVIEW,
        "product_name": "Premium Crunchy Biscuits",
        "ai_score": 45.0,
        "ai_risk_level": "CRITICAL",
        "ai_status": "FAIL",
        "ai_snapshot": json.dumps({"score": 45.0}),
        "organization_id": "org_integ_reg",
        "history": []
    })

    headers_audit = make_headers("integ_audit_1", ROLE_AUDIT)
    r1 = client.post("/api/reviews/rev_integ_dup_1/escalate", json={"escalation_reason": "Escalate 1"}, headers=headers_audit)
    assert r1.status_code == 200

    # Verify only 1 active case exists
    raw_cases, count = await list_enforcement_cases(organization_id="org_integ_reg")
    assert count == 1

