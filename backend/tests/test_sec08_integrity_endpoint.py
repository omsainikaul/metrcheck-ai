"""
Test Suite for SEC-AUD-08: Cryptographic Integrity Endpoint Authentication & Tenant Isolation.

Verifies:
TEST 1: Anonymous user requests integrity of a normal non-demo analysis -> 401 Unauthorized
TEST 2: Merchant A requests Merchant B's analysis integrity -> 403 Forbidden
TEST 3: Merchant A requests their own analysis integrity -> 200 OK
TEST 4: Authorized enforcement/audit officer requests an analysis belonging to their organization -> 200 OK
TEST 5: Officer from another organization requests the analysis -> 403 Forbidden
TEST 6: Admin requests another organization's analysis integrity -> 200 OK
TEST 7: Non-existent non-demo analysis ID (authenticated) -> 404 Not Found
TEST 8: Valid demo benchmark ID without authentication -> 200 OK
TEST 9: User without an organization cannot use the endpoint to access an unscoped legacy analysis -> 403 Forbidden (fail-closed)
TEST 10: Attempted cross-tenant access must not leak product name, score, status, system version, or integrity metadata
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import save_analysis, create_user, create_organization
from auth.security import (
    hash_password,
    create_token,
    ROLE_MERCHANT,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
)
from services.integrity_service import compute_analysis_integrity_hash


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _setup_sec_aud08_test_data():
    _ensure_test_isolation()

    # Create organizations
    await create_organization(id="org_sec_aud08_merchant_a", name="Merchant A Org", status="ACTIVE")
    await create_organization(id="org_sec_aud08_merchant_b", name="Merchant B Org", status="ACTIVE")
    await create_organization(id="org_sec_aud08_dept_a", name="Dept A Org", status="ACTIVE")
    await create_organization(id="org_sec_aud08_dept_b", name="Dept B Org", status="ACTIVE")
    await create_organization(id="org_ministry", name="Ministry Org", status="ACTIVE")

    # Create users
    pwh, salt = hash_password("Password123!")
    users = [
        ("sec_aud08_merchant_a", ROLE_MERCHANT, "org_sec_aud08_merchant_a"),
        ("sec_aud08_merchant_b", ROLE_MERCHANT, "org_sec_aud08_merchant_b"),
        ("sec_aud08_officer_a", ROLE_ENFORCEMENT, "org_sec_aud08_dept_a"),
        ("sec_aud08_officer_b", ROLE_ENFORCEMENT, "org_sec_aud08_dept_b"),
        ("sec_aud08_auditor_a", ROLE_AUDIT, "org_sec_aud08_dept_a"),
        ("sec_aud08_admin", ROLE_ADMIN, "org_ministry"),
        ("sec_aud08_no_org_user", ROLE_ENFORCEMENT, ""),
    ]
    for uname, role, org in users:
        try:
            await create_user(uname, pwh, salt, role, uname, organization_id=org)
        except Exception:
            pass

    # Record A: Owned by Merchant A in org_sec_aud08_merchant_a
    extracted_a = {"product_name": "Merchant A Secret Protein Bar", "net_quantity": "50 g"}
    comp_a = {"score": 95.0, "status": "COMPLIANT", "checks": []}
    hash_a = compute_analysis_integrity_hash(
        analysis_id="sec_aud08_analysis_a",
        product_name="Merchant A Secret Protein Bar",
        extracted_data=extracted_a,
        score=95.0,
        status="COMPLIANT",
        created_at="2026-09-19T10:00:00Z",
        compliance_result=comp_a
    )
    await save_analysis({
        "id": "sec_aud08_analysis_a",
        "product_name": "Merchant A Secret Protein Bar",
        "extracted_data": json.dumps(extracted_a),
        "compliance_result": json.dumps(comp_a),
        "score": 95.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-19T10:00:00Z",
        "owner_user_id": "sec_aud08_merchant_a",
        "organization_id": "org_sec_aud08_merchant_a",
        "integrity_hash": hash_a,
        "system_version": "2.4.0",
        "ocr_engine_version": "PaddleOCR PP-OCRv4",
        "ruleset_version": "2026.1"
    })

    # Record B: In org_sec_aud08_dept_a (for Department A officers)
    extracted_dept_a = {"product_name": "Dept A Inspection Sample", "net_quantity": "100 ml"}
    comp_dept_a = {"score": 60.0, "status": "NON_COMPLIANT", "checks": []}
    hash_dept_a = compute_analysis_integrity_hash(
        analysis_id="sec_aud08_analysis_dept_a",
        product_name="Dept A Inspection Sample",
        extracted_data=extracted_dept_a,
        score=60.0,
        status="NON_COMPLIANT",
        created_at="2026-09-19T11:00:00Z",
        compliance_result=comp_dept_a
    )
    await save_analysis({
        "id": "sec_aud08_analysis_dept_a",
        "product_name": "Dept A Inspection Sample",
        "extracted_data": json.dumps(extracted_dept_a),
        "compliance_result": json.dumps(comp_dept_a),
        "score": 60.0,
        "status": "NON_COMPLIANT",
        "created_at": "2026-09-19T11:00:00Z",
        "owner_user_id": "sec_aud08_officer_a",
        "organization_id": "org_sec_aud08_dept_a",
        "integrity_hash": hash_dept_a,
        "system_version": "2.4.0",
        "ocr_engine_version": "PaddleOCR PP-OCRv4",
        "ruleset_version": "2026.1"
    })

    # Legacy unscoped analysis
    await save_analysis({
        "id": "sec_aud08_legacy_unscoped",
        "product_name": "Legacy Unscoped Product",
        "extracted_data": json.dumps({"product_name": "Legacy Unscoped Product"}),
        "compliance_result": json.dumps({"score": 80.0, "status": "COMPLIANT", "checks": []}),
        "score": 80.0,
        "status": "COMPLIANT",
        "created_at": "2026-01-01T00:00:00Z",
        "owner_user_id": "",
        "organization_id": "",
        "integrity_hash": "legacy_hash",
    })


def _headers(username: str, role: str) -> dict:
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_01_anonymous_user_rejected_on_non_demo_analysis():
    """TEST 1: Anonymous user requesting integrity of a normal non-demo analysis returns 401 Unauthorized."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    resp = client.get("/api/history/sec_aud08_analysis_a/integrity")
    assert resp.status_code == 401
    assert "authentication required" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_02_merchant_a_requesting_merchant_b_analysis_integrity_forbidden():
    """TEST 2: Merchant A requesting Merchant B's analysis integrity returns 403 Forbidden."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    # Merchant B tries to access Merchant A's analysis
    resp = client.get(
        "/api/history/sec_aud08_analysis_a/integrity",
        headers=_headers("sec_aud08_merchant_b", ROLE_MERCHANT)
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_03_merchant_a_requesting_own_analysis_integrity_success():
    """TEST 3: Merchant A requesting their own analysis integrity returns 200 OK."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    resp = client.get(
        "/api/history/sec_aud08_analysis_a/integrity",
        headers=_headers("sec_aud08_merchant_a", ROLE_MERCHANT)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert "stored_hash" in data
    assert "computed_hash" in data
    assert data["system_version"] == "2.4.0"


@pytest.mark.asyncio
async def test_04_authorized_officer_same_organization_success():
    """TEST 4: Authorized enforcement/audit officer requesting an analysis belonging to their org returns 200 OK."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    # Officer A in org_sec_aud08_dept_a
    resp_enf = client.get(
        "/api/history/sec_aud08_analysis_dept_a/integrity",
        headers=_headers("sec_aud08_officer_a", ROLE_ENFORCEMENT)
    )
    assert resp_enf.status_code == 200
    assert resp_enf.json()["verified"] is True

    # Auditor A in org_sec_aud08_dept_a
    resp_aud = client.get(
        "/api/history/sec_aud08_analysis_dept_a/integrity",
        headers=_headers("sec_aud08_auditor_a", ROLE_AUDIT)
    )
    assert resp_aud.status_code == 200
    assert resp_aud.json()["verified"] is True


@pytest.mark.asyncio
async def test_05_officer_different_organization_forbidden():
    """TEST 5: Officer from another organization requesting the analysis returns 403 Forbidden."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    # Officer B is in org_sec_aud08_dept_b, resource is in org_sec_aud08_dept_a
    resp = client.get(
        "/api/history/sec_aud08_analysis_dept_a/integrity",
        headers=_headers("sec_aud08_officer_b", ROLE_ENFORCEMENT)
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_06_admin_cross_organization_success():
    """TEST 6: Admin requesting another organization's analysis integrity returns 200 OK."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    resp = client.get(
        "/api/history/sec_aud08_analysis_a/integrity",
        headers=_headers("sec_aud08_admin", ROLE_ADMIN)
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is True


@pytest.mark.asyncio
async def test_07_nonexistent_non_demo_analysis_id_returns_404():
    """TEST 7: Non-existent non-demo analysis ID returns 404 Not Found."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    resp = client.get(
        "/api/history/non_existent_uuid_12345/integrity",
        headers=_headers("sec_aud08_merchant_a", ROLE_MERCHANT)
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_08_valid_demo_benchmark_id_without_authentication_success():
    """TEST 8: Valid demo benchmark ID without authentication returns 200 OK with demo fixture."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    for demo_id in ["demo-1", "demo-2", "demo-3", "1", "2", "3"]:
        resp = client.get(f"/api/history/{demo_id}/integrity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data.get("is_demo_fixture") is True


@pytest.mark.asyncio
async def test_09_user_without_organization_fail_closed_on_unscoped_legacy():
    """TEST 9: User without an organization cannot use the endpoint to access unscoped legacy analysis (403)."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    resp = client.get(
        "/api/history/sec_aud08_legacy_unscoped/integrity",
        headers=_headers("sec_aud08_no_org_user", ROLE_ENFORCEMENT)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_10_cross_tenant_access_leaks_zero_metadata():
    """TEST 10: Attempted cross-tenant access must not leak product name, score, status, or integrity metadata."""
    await _setup_sec_aud08_test_data()
    client = TestClient(app)
    resp = client.get(
        "/api/history/sec_aud08_analysis_a/integrity",
        headers=_headers("sec_aud08_merchant_b", ROLE_MERCHANT)
    )
    assert resp.status_code == 403
    body_str = resp.text
    # Verify no sensitive commercial data from Record A is in the error body
    assert "Merchant A Secret Protein Bar" not in body_str
    assert "95.0" not in body_str
    assert "COMPLIANT" not in body_str
    assert "integrity_hash" not in body_str
    assert "computed_hash" not in body_str
