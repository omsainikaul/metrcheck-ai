"""
Test Suite for SEC-AUD-09: Evidence History Fail-Open / Missing Analysis Existence Validation.

Verifies:
TEST 1: Existing analysis + authorized merchant -> 200 OK
TEST 2: Existing analysis + same-organization officer -> 200 OK
TEST 3: Existing analysis + cross-tenant merchant -> 403 Forbidden
TEST 4: Existing analysis + cross-organization officer -> 403 Forbidden
TEST 5: Existing analysis + admin -> 200 OK
TEST 6: Nonexistent analysis ID -> 404 Not Found
TEST 7: Deleted/nonexistent analysis with orphan evidence audit logs -> 404 Not Found & NO audit records returned
TEST 8: Unscoped/legacy analysis + non-admin -> Fail closed (403 Forbidden)
TEST 9: Unauthorized requests do not expose audit entries, actor information, timestamps, correction/review details, or evidence metadata
TEST 10: Authorized evidence-history response format remains intact (analysis_id, logs, total_records)
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import (
    init_db,
    get_db,
    save_analysis,
    create_user,
    create_organization,
    save_evidence_audit_log,
)
from auth.security import (
    hash_password,
    create_token,
    ROLE_MERCHANT,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _setup_sec_aud09_test_data():
    _ensure_test_isolation()
    await init_db()

    # Clean existing test data for idempotency
    db = await get_db()
    await db.execute("DELETE FROM evidence_audit_logs WHERE analysis_id LIKE 'sec_aud09_%'")
    await db.execute("DELETE FROM analyses WHERE id LIKE 'sec_aud09_%'")
    await db.commit()

    # 1. Create organizations
    await create_organization(id="org_sec_aud09_merchant_a", name="Merchant A Org", status="ACTIVE")
    await create_organization(id="org_sec_aud09_merchant_b", name="Merchant B Org", status="ACTIVE")
    await create_organization(id="org_sec_aud09_dept_a", name="Dept A Org", status="ACTIVE")
    await create_organization(id="org_sec_aud09_dept_b", name="Dept B Org", status="ACTIVE")
    await create_organization(id="org_ministry", name="Ministry Org", status="ACTIVE")

    # 2. Create users
    pwh, salt = hash_password("Password123!")
    users = [
        ("sec_aud09_merchant_a", ROLE_MERCHANT, "org_sec_aud09_merchant_a"),
        ("sec_aud09_merchant_b", ROLE_MERCHANT, "org_sec_aud09_merchant_b"),
        ("sec_aud09_officer_a", ROLE_ENFORCEMENT, "org_sec_aud09_dept_a"),
        ("sec_aud09_officer_b", ROLE_ENFORCEMENT, "org_sec_aud09_dept_b"),
        ("sec_aud09_auditor_a", ROLE_AUDIT, "org_sec_aud09_dept_a"),
        ("sec_aud09_admin", ROLE_ADMIN, "org_ministry"),
        ("sec_aud09_no_org_user", ROLE_ENFORCEMENT, ""),
    ]
    for uname, role, org in users:
        try:
            await create_user(uname, pwh, salt, role, uname, organization_id=org)
        except Exception:
            pass

    # 3. Create analysis A (owned by Merchant A)
    extracted_a = {"product_name": "Merchant A Organic Cookies", "net_quantity": "200 g"}
    comp_a = {"score": 90.0, "status": "COMPLIANT", "checks": []}
    await save_analysis({
        "id": "sec_aud09_analysis_a",
        "product_name": "Merchant A Organic Cookies",
        "extracted_data": json.dumps(extracted_a),
        "compliance_result": json.dumps(comp_a),
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-19T10:00:00Z",
        "owner_user_id": "sec_aud09_merchant_a",
        "organization_id": "org_sec_aud09_merchant_a",
    })

    # Save evidence audit logs for analysis A
    await save_evidence_audit_log(
        analysis_id="sec_aud09_analysis_a",
        evidence_id="ev_a_1",
        rule_id="RULE_NET_QTY",
        actor_username="sec_aud09_merchant_a",
        action_type="CORRECTION",
        previous_value="150 g",
        new_value="200 g",
        comments="Updated net weight to match package label",
        organization_id="org_sec_aud09_merchant_a",
    )

    # 4. Create analysis Dept A (belonging to Dept A)
    extracted_dept_a = {"product_name": "Dept A Inspection Sample", "net_quantity": "500 ml"}
    comp_dept_a = {"score": 75.0, "status": "NON_COMPLIANT", "checks": []}
    await save_analysis({
        "id": "sec_aud09_analysis_dept_a",
        "product_name": "Dept A Inspection Sample",
        "extracted_data": json.dumps(extracted_dept_a),
        "compliance_result": json.dumps(comp_dept_a),
        "score": 75.0,
        "status": "NON_COMPLIANT",
        "created_at": "2026-09-19T11:00:00Z",
        "owner_user_id": "sec_aud09_officer_a",
        "organization_id": "org_sec_aud09_dept_a",
    })

    # Save evidence audit logs for Dept A analysis
    await save_evidence_audit_log(
        analysis_id="sec_aud09_analysis_dept_a",
        evidence_id="ev_dept_1",
        rule_id="RULE_MRP",
        actor_username="sec_aud09_officer_a",
        action_type="APPROVE",
        previous_value="NEEDS_REVIEW",
        new_value="PASS",
        comments="Officer verified MRP font size compliance",
        organization_id="org_sec_aud09_dept_a",
    )

    # 5. Create orphan audit log for non-existent analysis "sec_aud09_orphan_analysis"
    await save_evidence_audit_log(
        analysis_id="sec_aud09_orphan_analysis",
        evidence_id="ev_orphan_1",
        rule_id="RULE_MFG_DATE",
        actor_username="deleted_user",
        action_type="CORRECTION",
        previous_value="01/2025",
        new_value="02/2025",
        comments="Orphaned audit entry without active analysis parent",
        organization_id="org_sec_aud09_dept_a",
    )

    # 6. Create legacy unscoped analysis (empty organization_id)
    await save_analysis({
        "id": "sec_aud09_legacy_unscoped",
        "product_name": "Legacy Unscoped Product",
        "extracted_data": json.dumps({"product_name": "Legacy Product"}),
        "compliance_result": json.dumps({"score": 50.0, "status": "FAIL"}),
        "score": 50.0,
        "status": "FAIL",
        "created_at": "2026-09-19T12:00:00Z",
        "owner_user_id": "legacy_user",
        "organization_id": "",
    })
    await save_evidence_audit_log(
        analysis_id="sec_aud09_legacy_unscoped",
        evidence_id="ev_legacy_1",
        rule_id="RULE_GENERIC",
        actor_username="legacy_user",
        action_type="REVIEW",
        previous_value="UNVERIFIED",
        new_value="FAIL",
        comments="Legacy unscoped entry",
        organization_id="",
    )


def _get_headers(username: str, role: str, org_id: str = "") -> dict:
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_01_existing_analysis_authorized_merchant():
    """TEST 1: Existing analysis + authorized merchant -> 200 OK."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_merchant_a", ROLE_MERCHANT, "org_sec_aud09_merchant_a")

    response = client.get("/api/evidence/sec_aud09_analysis_a/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == "sec_aud09_analysis_a"
    assert data["total_records"] == 1
    assert len(data["logs"]) == 1
    assert data["logs"][0]["evidence_id"] == "ev_a_1"
    assert data["logs"][0]["actor_username"] == "sec_aud09_merchant_a"


@pytest.mark.asyncio
async def test_02_existing_analysis_same_org_officer():
    """TEST 2: Existing analysis + same-organization officer -> 200 OK."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_officer_a", ROLE_ENFORCEMENT, "org_sec_aud09_dept_a")

    response = client.get("/api/evidence/sec_aud09_analysis_dept_a/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_id"] == "sec_aud09_analysis_dept_a"
    assert data["total_records"] == 1
    assert data["logs"][0]["actor_username"] == "sec_aud09_officer_a"


@pytest.mark.asyncio
async def test_03_existing_analysis_cross_tenant_merchant():
    """TEST 3: Existing analysis + cross-tenant merchant -> 403 Forbidden."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_merchant_b", ROLE_MERCHANT, "org_sec_aud09_merchant_b")

    response = client.get("/api/evidence/sec_aud09_analysis_a/history", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_04_existing_analysis_cross_org_officer():
    """TEST 4: Existing analysis + cross-organization officer -> 403 Forbidden."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_officer_b", ROLE_ENFORCEMENT, "org_sec_aud09_dept_b")

    response = client.get("/api/evidence/sec_aud09_analysis_dept_a/history", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_05_existing_analysis_admin():
    """TEST 5: Existing analysis + admin -> 200 OK (Supervisory oversight)."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_admin", ROLE_ADMIN, "org_ministry")

    # Admin accessing Merchant A's evidence history
    response = client.get("/api/evidence/sec_aud09_analysis_a/history", headers=headers)
    assert response.status_code == 200
    assert response.json()["analysis_id"] == "sec_aud09_analysis_a"

    # Admin accessing Dept A's evidence history
    response_dept = client.get("/api/evidence/sec_aud09_analysis_dept_a/history", headers=headers)
    assert response_dept.status_code == 200
    assert response_dept.json()["analysis_id"] == "sec_aud09_analysis_dept_a"


@pytest.mark.asyncio
async def test_06_nonexistent_analysis_id():
    """TEST 6: Nonexistent analysis ID -> 404 Not Found."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_officer_a", ROLE_ENFORCEMENT, "org_sec_aud09_dept_a")

    response = client.get("/api/evidence/sec_aud09_completely_nonexistent/history", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis not found"


@pytest.mark.asyncio
async def test_07_deleted_nonexistent_analysis_with_orphan_evidence_logs():
    """TEST 7: Deleted/nonexistent analysis with orphan evidence audit logs -> 404 and NO audit records returned."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_officer_a", ROLE_ENFORCEMENT, "org_sec_aud09_dept_a")

    # The orphan analysis "sec_aud09_orphan_analysis" exists only in evidence_audit_logs, NOT in analyses table
    response = client.get("/api/evidence/sec_aud09_orphan_analysis/history", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis not found"
    # Ensure no evidence audit records are returned in the response body
    assert "logs" not in response.json()


@pytest.mark.asyncio
async def test_08_unscoped_legacy_analysis_fail_closed():
    """TEST 8: Unscoped/legacy analysis + non-admin -> fail closed (403 Forbidden)."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_officer_a", ROLE_ENFORCEMENT, "org_sec_aud09_dept_a")

    # Scoped officer cannot access unassigned/unscoped legacy resource
    response = client.get("/api/evidence/sec_aud09_legacy_unscoped/history", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_09_unauthorized_requests_zero_metadata_leakage():
    """TEST 9: Verify that unauthorized requests do not expose audit entries, actor information, timestamps, or comments."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_merchant_b", ROLE_MERCHANT, "org_sec_aud09_merchant_b")

    response = client.get("/api/evidence/sec_aud09_analysis_a/history", headers=headers)
    assert response.status_code == 403
    raw_body = response.text
    # Sensitive evidence audit data must not appear anywhere in error body
    assert "ev_a_1" not in raw_body
    assert "sec_aud09_merchant_a" not in raw_body
    assert "Updated net weight" not in raw_body
    assert "200 g" not in raw_body


@pytest.mark.asyncio
async def test_10_authorized_response_schema_integrity():
    """TEST 10: Verify existing authorized evidence-history response format remains unchanged."""
    await _setup_sec_aud09_test_data()
    client = TestClient(app)
    headers = _get_headers("sec_aud09_officer_a", ROLE_ENFORCEMENT, "org_sec_aud09_dept_a")

    response = client.get("/api/evidence/sec_aud09_analysis_dept_a/history", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Schema checks
    assert "analysis_id" in data
    assert "logs" in data
    assert "total_records" in data
    assert isinstance(data["logs"], list)
    assert data["total_records"] == len(data["logs"])

    log_entry = data["logs"][0]
    expected_fields = [
        "id", "analysis_id", "evidence_id", "rule_id", "actor_username",
        "action_type", "previous_value", "new_value", "comments", "created_at"
    ]
    for field in expected_fields:
        assert field in log_entry, f"Missing expected field: {field}"
    assert log_entry["action_type"] == "APPROVE"
    assert log_entry["comments"] == "Officer verified MRP font size compliance"
