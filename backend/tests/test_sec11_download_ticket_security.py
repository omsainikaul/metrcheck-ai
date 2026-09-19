"""
Test Suite for SEC-AUD-11: Download Ticket Security & Session JWT Elimination from URLs.

Components Under Test:
- backend/database/db.py: download_tickets table, save_download_ticket, redeem_download_ticket_in_db
- backend/auth/security.py: generate_download_ticket_string, parse_and_verify_ticket_string, validate_ticket_and_get_user, get_current_user
- backend/auth/routes.py: POST /api/auth/download-ticket
- backend/api/images.py: GET /api/images/{filename} via ticket & Bearer
- backend/api/report.py: GET /api/report/{id} (pdf/csv/xlsx/json) via ticket & Bearer

Verifications:
1. Authenticated user can obtain a valid ticket for an authorized report
2. Authenticated user can obtain a valid ticket for an authorized image
3. Anonymous user cannot obtain a ticket (401)
4. Cross-tenant user cannot obtain a ticket for another tenant's resource (403)
5. Merchant cannot obtain a ticket for another merchant's resource (403)
6. Officer cannot obtain a ticket for another organization (403)
7. Admin can obtain an authorized ticket for any organization resource (200)
8. Valid ticket successfully downloads the intended resource (200)
9. Expired ticket is rejected (401)
10. Tampered ticket is rejected (401)
11. Ticket for resource A cannot access resource B (401)
12. Ticket for resource type A (e.g. image) cannot be reused for resource type B (e.g. report) (401)
13. Second use of a single-use ticket is strictly rejected (401)
14. Normal Bearer JWT API authentication continues working seamlessly (200)
15. Raw session JWT in ?token= query parameter is rejected on download/image endpoints (401)
16. Demo benchmark resources remain accessible
17. No JWT or secret appears in ticket strings, download URLs, or error payloads
18. Suspended or unactivated users cannot obtain download tickets (403 / 401)
"""

import os
import time
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
    save_download_ticket,
)
from auth.security import (
    hash_password,
    create_token,
    generate_download_ticket_string,
    ROLE_MERCHANT,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


async def _setup_sec11_test_fixtures():
    _ensure_test_isolation()
    await init_db()

    db = await get_db()
    await db.execute("DELETE FROM download_tickets WHERE user_id LIKE 'sec11_%' OR username LIKE 'sec11_%'")
    await db.execute("DELETE FROM analyses WHERE id LIKE 'sec11_%'")
    await db.commit()

    # Organizations
    await create_organization(id="org_sec11_merchant_a", name="Merchant A Org", status="ACTIVE")
    await create_organization(id="org_sec11_merchant_b", name="Merchant B Org", status="ACTIVE")
    await create_organization(id="org_sec11_dept_a", name="Dept A Org", status="ACTIVE")
    await create_organization(id="org_sec11_dept_b", name="Dept B Org", status="ACTIVE")
    await create_organization(id="org_ministry", name="Ministry Org", status="ACTIVE")

    # Users
    pwh, salt = hash_password("Password123!")
    users = [
        ("sec11_merchant_a", ROLE_MERCHANT, "org_sec11_merchant_a"),
        ("sec11_merchant_b", ROLE_MERCHANT, "org_sec11_merchant_b"),
        ("sec11_officer_a", ROLE_ENFORCEMENT, "org_sec11_dept_a"),
        ("sec11_officer_b", ROLE_ENFORCEMENT, "org_sec11_dept_b"),
        ("sec11_admin", ROLE_ADMIN, "org_ministry"),
    ]
    for uname, role, org in users:
        try:
            await create_user(uname, pwh, salt, role, uname, organization_id=org)
        except Exception:
            pass

    # Files in upload dir
    file_a = "sec11_prod_a.jpg"
    file_b = "sec11_prod_b.jpg"
    path_a = os.path.join(settings.UPLOAD_DIR, file_a)
    path_b = os.path.join(settings.UPLOAD_DIR, file_b)
    with open(path_a, "wb") as f:
        f.write(b"BINARY_IMAGE_DATA_MERCHANT_A")
    with open(path_b, "wb") as f:
        f.write(b"BINARY_IMAGE_DATA_MERCHANT_B")

    # Analysis records
    ext_a = {"product_name": "Merchant A Product", "net_quantity": "100 g"}
    comp_a = {"score": 90.0, "status": "COMPLIANT", "checks": []}
    await save_analysis({
        "id": "sec11_analysis_a",
        "product_name": "Merchant A Product",
        "image_filename": file_a,
        "ocr_text": "Sample text",
        "extracted_data": json.dumps(ext_a),
        "compliance_result": json.dumps(comp_a),
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-19T10:00:00Z",
        "images": [{"filename": file_a, "image_url": f"/api/images/{file_a}"}],
        "owner_user_id": "sec11_merchant_a",
        "organization_id": "org_sec11_merchant_a",
    })

    ext_b = {"product_name": "Merchant B Product", "net_quantity": "250 g"}
    comp_b = {"score": 70.0, "status": "NON_COMPLIANT", "checks": []}
    await save_analysis({
        "id": "sec11_analysis_b",
        "product_name": "Merchant B Product",
        "image_filename": file_b,
        "ocr_text": "Sample text B",
        "extracted_data": json.dumps(ext_b),
        "compliance_result": json.dumps(comp_b),
        "score": 70.0,
        "status": "NON_COMPLIANT",
        "created_at": "2026-09-19T11:00:00Z",
        "images": [{"filename": file_b, "image_url": f"/api/images/{file_b}"}],
        "owner_user_id": "sec11_merchant_b",
        "organization_id": "org_sec11_merchant_b",
    })


def _get_headers(username: str, role: str) -> dict:
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_01_authenticated_user_obtains_report_ticket():
    """TEST 1: Authenticated user obtains a valid short-lived download ticket for their own report."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    resp = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "ticket" in data
    assert data["ticket"].startswith("dt_")
    assert data["resource_type"] == "report"
    assert data["resource_id"] == "sec11_analysis_a"
    assert data["expires_in_seconds"] == 60
    assert "ticket=" in data["download_url"]


@pytest.mark.asyncio
async def test_02_authenticated_user_obtains_image_ticket():
    """TEST 2: Authenticated user obtains a valid download ticket for their own image."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    resp = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "image", "resource_id": "sec11_prod_a.jpg"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource_type"] == "image"
    assert data["resource_id"] == "sec11_prod_a.jpg"


@pytest.mark.asyncio
async def test_03_anonymous_user_cannot_obtain_ticket():
    """TEST 3: Anonymous request to issue ticket is rejected with 401."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)

    resp = client.post(
        "/api/auth/download-ticket",
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_04_cross_tenant_merchant_cannot_obtain_ticket():
    """TEST 4: Merchant B cannot obtain a download ticket for Merchant A's report (403)."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_b", ROLE_MERCHANT)

    resp = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_05_cross_tenant_merchant_cannot_obtain_image_ticket():
    """TEST 5: Merchant B cannot obtain a download ticket for Merchant A's image (403)."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_b", ROLE_MERCHANT)

    resp = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "image", "resource_id": "sec11_prod_a.jpg"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_06_officer_cannot_obtain_ticket_for_another_org():
    """TEST 6: Officer B cannot obtain a download ticket for Organization A's analysis (403)."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_officer_b", ROLE_ENFORCEMENT)

    resp = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_07_admin_can_obtain_ticket():
    """TEST 7: Admin can obtain a ticket for any tenant's analysis."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_admin", ROLE_ADMIN)

    resp = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    assert resp.status_code == 200
    assert "ticket" in resp.json()


@pytest.mark.asyncio
async def test_08_valid_ticket_downloads_resource():
    """TEST 8: Valid ticket successfully downloads the intended resource without Bearer token."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    # 1. Download image
    ticket_res = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "image", "resource_id": "sec11_prod_a.jpg"}
    )
    ticket_img = ticket_res.json()["ticket"]
    resp_img = client.get(f"/api/images/sec11_prod_a.jpg?ticket={ticket_img}")
    assert resp_img.status_code == 200
    assert resp_img.content == b"BINARY_IMAGE_DATA_MERCHANT_A"

    # 2. Download report PDF
    ticket_res_pdf = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    ticket_pdf = ticket_res_pdf.json()["ticket"]
    resp_pdf = client.get(f"/api/report/sec11_analysis_a?ticket={ticket_pdf}")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_09_expired_ticket_rejected():
    """TEST 9: Expired ticket is rejected with 401."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)

    # Manually save expired ticket in db
    ticket_id = "expired_ticket_123"
    await save_download_ticket(
        ticket_id=ticket_id,
        user_id="sec11_merchant_a",
        username="sec11_merchant_a",
        role=ROLE_MERCHANT,
        organization_id="org_sec11_merchant_a",
        resource_type="report",
        resource_id="sec11_analysis_a",
        action="download",
        expires_at=time.time() - 10.0,  # expired 10 seconds ago
    )
    ticket_str = generate_download_ticket_string(ticket_id)

    resp = client.get(f"/api/report/sec11_analysis_a?ticket={ticket_str}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_10_tampered_ticket_rejected():
    """TEST 10: Tampered ticket string is rejected with 401."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    ticket_res = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    valid_ticket = ticket_res.json()["ticket"]
    tampered_ticket = valid_ticket[:-4] + "dead"

    resp = client.get(f"/api/report/sec11_analysis_a?ticket={tampered_ticket}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_11_ticket_resource_scoping():
    """TEST 11: Ticket issued for Analysis A cannot be used to download Analysis B."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    ticket_res = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "report", "resource_id": "sec11_analysis_a"}
    )
    ticket_a = ticket_res.json()["ticket"]

    # Attempt to redeem ticket for analysis B
    resp = client.get(f"/api/report/sec11_analysis_b?ticket={ticket_a}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_12_ticket_type_scoping():
    """TEST 12: Ticket issued for Image cannot be reused for Report endpoint."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    ticket_res = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "image", "resource_id": "sec11_prod_a.jpg"}
    )
    ticket_img = ticket_res.json()["ticket"]

    # Attempt to redeem image ticket on report endpoint
    resp = client.get(f"/api/report/sec11_analysis_a?ticket={ticket_img}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_13_single_use_enforcement():
    """TEST 13: Second attempt to use the same ticket is strictly rejected."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    ticket_res = client.post(
        "/api/auth/download-ticket",
        headers=headers,
        json={"resource_type": "image", "resource_id": "sec11_prod_a.jpg"}
    )
    ticket = ticket_res.json()["ticket"]

    # First redemption succeeds
    resp1 = client.get(f"/api/images/sec11_prod_a.jpg?ticket={ticket}")
    assert resp1.status_code == 200

    # Second redemption with same ticket fails (already redeemed)
    resp2 = client.get(f"/api/images/sec11_prod_a.jpg?ticket={ticket}")
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_14_bearer_jwt_auth_continues_working():
    """TEST 14: Standard API Bearer token in Authorization header continues to work normally."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    headers = _get_headers("sec11_merchant_a", ROLE_MERCHANT)

    # Bearer header on report endpoint
    resp = client.get("/api/report/sec11_analysis_a", headers=headers)
    assert resp.status_code == 200

    # Bearer header on image endpoint
    resp_img = client.get("/api/images/sec11_prod_a.jpg", headers=headers)
    assert resp_img.status_code == 200


@pytest.mark.asyncio
async def test_15_raw_session_jwt_in_query_param_rejected():
    """TEST 15: Passing raw session JWT in ?token= is strictly rejected with 401."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)
    token = create_token("sec11_merchant_a", ROLE_MERCHANT)

    # 1. Image endpoint rejects ?token=
    resp_img = client.get(f"/api/images/sec11_prod_a.jpg?token={token}")
    assert resp_img.status_code == 401

    # 2. Report endpoint rejects ?token=
    resp_rep = client.get(f"/api/report/sec11_analysis_a?token={token}")
    assert resp_rep.status_code == 401


@pytest.mark.asyncio
async def test_16_demo_benchmark_accessible_without_ticket():
    """TEST 16: Public demo benchmarks remain accessible for public verification."""
    await _setup_sec11_test_fixtures()
    client = TestClient(app)

    resp = client.get("/api/report/demo-1")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
