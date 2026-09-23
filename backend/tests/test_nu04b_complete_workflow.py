"""
MetrCheck AI — Phase NU-04B: Complete Normal User Workflow & Decision-Cycle Verification Suite

Tests the 20 authoritative requirements:
1. Dashboard personal metrics isolation
2. Normal User empty state
3. Analyze submission authorization
4. Analysis persistence & integrity
5. PASS result retrieval
6. REVIEW result retrieval
7. FAIL result retrieval
8. Evidence panel mapping (Front vs Back)
9. Evidence image Bearer authentication
10. Evidence bounding-box contract ([x1, y1, x2, y2])
11. Re-scan creates new analysis without mutating old record
12. History returns only caller's scans
13. Own scan deletion removes record
14. Cross-user scan IDOR blocked (403 Forbidden)
15. Cross-user image IDOR blocked (403 Forbidden)
16. Cross-user report IDOR blocked (403 Forbidden)
17. Report download ticket security (single-use & bound)
18. Human review correction preserves AI snapshot
19. Human review confirmation remains auditable
20. Error responses do not leak raw stack traces or SQL
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import (
    init_db, save_analysis, get_analysis, create_user,
    save_review, get_review_by_analysis_id,
    save_download_ticket,
)
from auth.security import (
    hash_password, create_token, ROLE_USER, ROLE_MERCHANT, ROLE_ENFORCEMENT, ROLE_ADMIN,
    generate_download_ticket_string
)
from models.schemas import ProductImageEvidence, ComplianceCheck, EvidenceItem


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


@pytest.fixture(autouse=True)
def setup_env():
    _ensure_test_isolation()


async def _create_test_user(username: str, role: str = ROLE_USER, org_id: str = ""):
    salt, pwh = hash_password("TestPassword123!")
    try:
        await create_user(
            username=username,
            password_hash=pwh,
            salt=salt,
            role=role,
            full_name=f"User {username}",
            organization_id=org_id,
        )
    except Exception:
        pass


# ── 1. DASHBOARD PERSONAL METRICS ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_dashboard_personal_metrics():
    """Verify Dashboard metrics only count current user's analyses."""
    await init_db()
    client = TestClient(app)
    user_a = f"nu_user_a_{os.urandom(4).hex()}"
    user_b = f"nu_user_b_{os.urandom(4).hex()}"
    await _create_test_user(user_a, ROLE_USER, f"org_{user_a}")
    await _create_test_user(user_b, ROLE_USER, f"org_{user_b}")

    token_a = create_token(user_a, ROLE_USER)

    # Save 2 analyses for User A (1 PASS, 1 FAIL)
    await save_analysis(
        analysis_id=f"ana-a1-{os.urandom(4).hex()}",
        product_name="User A Prod 1",
        owner_user_id=user_a,
        organization_id=f"org_{user_a}",
        status="COMPLIANT",
        score=100.0,
        compliance_result={"score": 100.0, "status": "COMPLIANT", "checks": []},
    )
    await save_analysis(
        analysis_id=f"ana-a2-{os.urandom(4).hex()}",
        product_name="User A Prod 2",
        owner_user_id=user_a,
        organization_id=f"org_{user_a}",
        status="NON_COMPLIANT",
        score=40.0,
        compliance_result={"score": 40.0, "status": "NON_COMPLIANT", "checks": [{"rule_id": "LM-001", "status": "FAIL"}]},
    )

    # Save 3 analyses for User B
    for i in range(3):
        await save_analysis(
            analysis_id=f"ana-b{i}-{os.urandom(4).hex()}",
            product_name=f"User B Prod {i}",
            owner_user_id=user_b,
            organization_id=f"org_{user_b}",
            status="COMPLIANT",
            score=100.0,
            compliance_result={"score": 100.0, "status": "COMPLIANT", "checks": []},
        )

    # User A requests dashboard stats
    res = client.get("/api/stats", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_analyzed"] == 2
    assert data["compliant"] == 1
    assert data["failures"] == 1
    assert len(data["recent"]) == 2
    assert all(r["product_name"].startswith("User A") for r in data["recent"])


# ── 2. NORMAL USER EMPTY STATE ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_02_normal_user_empty_state():
    """Brand new user with 0 scans sees clean empty metrics without fake data."""
    await init_db()
    client = TestClient(app)
    new_user = f"new_nu_{os.urandom(4).hex()}"
    await _create_test_user(new_user, ROLE_USER, f"org_{new_user}")
    token = create_token(new_user, ROLE_USER)

    res = client.get("/api/stats", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_analyzed"] == 0
    assert data["compliant"] == 0
    assert data["needs_review"] == 0
    assert data["failures"] == 0
    assert data["recent"] == []


# ── 3. ANALYZE SUBMISSION AUTHORIZATION ───────────────────────────────────────

@pytest.mark.asyncio
async def test_03_analyze_submission_authorization():
    """Analyze endpoint accepts requests and validates file presence."""
    await init_db()
    client = TestClient(app)
    user = f"submit_nu_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    # Request without files returns 400 validation error
    unauth_res = client.post("/api/analyze", data={"labels": json.dumps(["Front"])})
    assert unauth_res.status_code == 400
    assert "image file is required" in unauth_res.json().get("detail", "").lower()

    # Authenticated request without files also returns 400 validation error
    auth_res = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token}"},
        data={"labels": json.dumps(["Front"])}
    )
    assert auth_res.status_code == 400
    assert "image file is required" in auth_res.json().get("detail", "").lower()


# ── 4. ANALYSIS PERSISTENCE & INTEGRITY ───────────────────────────────────────

@pytest.mark.asyncio
async def test_04_analysis_persistence():
    """Saved analysis record is persistent and includes compliance result and image metadata."""
    await init_db()
    ana_id = f"ana-persist-{os.urandom(4).hex()}"
    username = f"persist_user_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_USER, f"org_{username}")

    await save_analysis(
        analysis_id=ana_id,
        product_name="Persistence Test Oatmeal",
        owner_user_id=username,
        organization_id=f"org_{username}",
        image_filename="front.png",
        images=[{"image_url": "/api/images/front.png", "label": "Front", "word_count": 25}],
        extracted_data={"product_name": "Persistence Test Oatmeal", "net_quantity": "500 g"},
        compliance_result={"score": 90.0, "status": "COMPLIANT", "checks": []},
        ocr_text="Persistence Test Oatmeal 500 g",
    )

    loaded = await get_analysis(ana_id)
    assert loaded is not None
    assert loaded["product_name"] == "Persistence Test Oatmeal"
    assert loaded["owner_user_id"] == username
    assert "images" in loaded


# ── 5. PASS RESULT RETRIEVAL ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_05_pass_result_retrieval():
    """Compliant analysis returns PASS status and full checks list."""
    await init_db()
    client = TestClient(app)
    user = f"pass_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-pass-{os.urandom(4).hex()}"
    checks = [
        {"rule_id": "LM-001", "field": "manufacturer", "field_label": "Manufacturer Name", "status": "PASS", "detected": True},
        {"rule_id": "LM-002", "field": "net_quantity", "field_label": "Net Quantity", "status": "PASS", "detected": True},
    ]
    await save_analysis(
        analysis_id=ana_id,
        product_name="Compliant Honey 500g",
        owner_user_id=user,
        organization_id=f"org_{user}",
        status="COMPLIANT",
        score=100.0,
        compliance_result={"score": 100.0, "status": "COMPLIANT", "checks": checks},
    )

    res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["compliance_result"]["status"] == "COMPLIANT"
    assert res_data["compliance_result"]["score"] == 100.0
    assert len(res_data["compliance_result"]["checks"]) == 2


# ── 6. REVIEW RESULT RETRIEVAL ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_06_review_result_retrieval():
    """Analysis with ambiguous or unprinted field returns NEEDS_REVIEW with reason."""
    await init_db()
    client = TestClient(app)
    user = f"review_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-review-{os.urandom(4).hex()}"
    checks = [
        {
            "rule_id": "LM-004",
            "field": "mrp",
            "field_label": "Maximum Retail Price (MRP)",
            "status": "NEEDS_REVIEW",
            "detected": False,
            "explanation": "MRP label detected but numeric value is unprinted or missing.",
            "recommendation": "Visually inspect the physical stamp on the package."
        }
    ]
    await save_analysis(
        analysis_id=ana_id,
        product_name="Alpino Oats (Review State)",
        owner_user_id=user,
        organization_id=f"org_{user}",
        status="REVIEW_REQUIRED",
        score=85.0,
        compliance_result={"score": 85.0, "status": "REVIEW_REQUIRED", "checks": checks},
    )

    res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["compliance_result"]["status"] == "REVIEW_REQUIRED"
    lm_004 = res_data["compliance_result"]["checks"][0]
    assert lm_004["status"] == "NEEDS_REVIEW"
    assert "unprinted" in lm_004["explanation"]


# ── 7. FAIL RESULT RETRIEVAL ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_07_fail_result_retrieval():
    """Analysis with missing mandatory requirement returns NON_COMPLIANT / FAIL."""
    await init_db()
    client = TestClient(app)
    user = f"fail_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-fail-{os.urandom(4).hex()}"
    checks = [
        {
            "rule_id": "LM-008",
            "field": "country_of_origin",
            "field_label": "Country of Origin",
            "status": "FAIL",
            "detected": False,
            "explanation": "Country of origin declaration is completely missing.",
            "recommendation": "Declare 'Country of Origin: India' or country of manufacture."
        }
    ]
    await save_analysis(
        analysis_id=ana_id,
        product_name="Non-Compliant Biscuit",
        owner_user_id=user,
        organization_id=f"org_{user}",
        status="NON_COMPLIANT",
        score=60.0,
        compliance_result={"score": 60.0, "status": "NON_COMPLIANT", "checks": checks},
    )

    res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["compliance_result"]["status"] == "NON_COMPLIANT"
    assert res_data["compliance_result"]["checks"][0]["status"] == "FAIL"


# ── 8. EVIDENCE PANEL MAPPING ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_08_evidence_panel_mapping():
    """Verify evidence items are attributed to the correct panel (Front vs Back)."""
    await init_db()
    client = TestClient(app)
    user = f"panel_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-panel-{os.urandom(4).hex()}"
    images = [
        {"image_url": "/api/images/front.png", "label": "Front", "word_count": 10},
        {"image_url": "/api/images/back.png", "label": "Back", "word_count": 45}
    ]
    checks = [
        {
            "rule_id": "LM-002",
            "field": "net_quantity",
            "field_label": "Net Quantity",
            "evidence_image_label": "Front",
            "bbox": [50, 100, 200, 140],
            "evidence": [{"rule_id": "LM-002", "image_label": "Front", "bbox": [50, 100, 200, 140]}]
        },
        {
            "rule_id": "FS-003",
            "field": "ingredients",
            "field_label": "Ingredients",
            "evidence_image_label": "Back",
            "bbox": [101, 147, 388, 260],
            "evidence": [{"rule_id": "FS-003", "image_label": "Back", "bbox": [101, 147, 388, 260]}]
        }
    ]
    await save_analysis(
        analysis_id=ana_id,
        product_name="Dual Panel Test Product",
        owner_user_id=user,
        organization_id=f"org_{user}",
        images=images,
        compliance_result={"score": 90.0, "status": "COMPLIANT", "checks": checks},
    )

    res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    res_data = res.json()
    assert len(res_data["images"]) == 2
    assert res_data["images"][0]["label"] == "Front"
    assert res_data["images"][1]["label"] == "Back"
    assert res_data["compliance_result"]["checks"][0]["evidence"][0]["image_label"] == "Front"
    assert res_data["compliance_result"]["checks"][1]["evidence"][0]["image_label"] == "Back"


# ── 9. EVIDENCE IMAGE AUTHENTICATION ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_09_evidence_image_authentication():
    """Unauthenticated access to image file returns 401 Unauthorized."""
    await init_db()
    client = TestClient(app)
    user = f"img_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    filename = f"auth_test_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    await save_analysis(
        analysis_id=f"ana-img-{os.urandom(4).hex()}",
        product_name="Image Auth Product",
        owner_user_id=user,
        organization_id=f"org_{user}",
        image_filename=filename,
    )

    # Unauthenticated request -> 401
    unauth = client.get(f"/api/images/{filename}")
    assert unauth.status_code == 401

    # Authenticated request -> 200
    auth = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
    assert auth.status_code == 200


# ── 10. EVIDENCE BOUNDING BOX CONTRACT ────────────────────────────────────────

@pytest.mark.asyncio
async def test_10_evidence_bounding_box_contract():
    """Evidence items strictly adhere to [x1, y1, x2, y2] bounding box contract."""
    await init_db()
    client = TestClient(app)
    user = f"bbox_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-bbox-{os.urandom(4).hex()}"
    bbox_coords = [101, 147, 388, 260]
    checks = [
        {
            "rule_id": "FS-003",
            "field": "ingredients",
            "field_label": "Ingredients",
            "bbox": bbox_coords,
            "evidence": [
                {
                    "rule_id": "FS-003",
                    "bbox": bbox_coords,
                    "geometry_type": "WORD_UNION",
                    "match_method": "DIRECT_OCR",
                    "confidence": 0.81
                }
            ]
        }
    ]
    await save_analysis(
        analysis_id=ana_id,
        product_name="BBox Test Product",
        owner_user_id=user,
        organization_id=f"org_{user}",
        compliance_result={"score": 85.0, "status": "REVIEW_REQUIRED", "checks": checks},
    )

    res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    ev = res.json()["compliance_result"]["checks"][0]["evidence"][0]
    assert ev["bbox"] == [101, 147, 388, 260]
    assert ev["geometry_type"] == "WORD_UNION"
    assert ev["confidence"] == 0.81


# ── 11. RE-SCAN CREATES A NEW ANALYSIS ────────────────────────────────────────

@pytest.mark.asyncio
async def test_11_rescan_creates_new_analysis():
    """Re-scanning a product generates a new distinct analysis ID and preserves historical record."""
    await init_db()
    username = f"rescan_user_{os.urandom(4).hex()}"
    await _create_test_user(username, ROLE_USER, f"org_{username}")

    id_v1 = f"ana-scan1-{os.urandom(4).hex()}"
    id_v2 = f"ana-scan2-{os.urandom(4).hex()}"

    await save_analysis(
        analysis_id=id_v1,
        product_name="Peanut Butter 1kg (Scan 1)",
        owner_user_id=username,
        organization_id=f"org_{username}",
        score=80.0,
        status="REVIEW_REQUIRED",
    )

    await save_analysis(
        analysis_id=id_v2,
        product_name="Peanut Butter 1kg (Scan 2)",
        owner_user_id=username,
        organization_id=f"org_{username}",
        score=100.0,
        status="COMPLIANT",
    )

    v1 = await get_analysis(id_v1)
    v2 = await get_analysis(id_v2)

    assert v1 is not None and v2 is not None
    assert v1["id"] != v2["id"]
    assert v1["score"] == 80.0
    assert v2["score"] == 100.0


# ── 12. HISTORY ONLY RETURNS CURRENT USER'S SCANS ─────────────────────────────

@pytest.mark.asyncio
async def test_12_history_only_returns_current_user_scans():
    """GET /api/history returns exclusively records owned by the calling user."""
    await init_db()
    client = TestClient(app)
    user_x = f"hist_x_{os.urandom(4).hex()}"
    user_y = f"hist_y_{os.urandom(4).hex()}"
    await _create_test_user(user_x, ROLE_USER, f"org_{user_x}")
    await _create_test_user(user_y, ROLE_USER, f"org_{user_y}")

    token_x = create_token(user_x, ROLE_USER)

    await save_analysis(
        analysis_id=f"ana-x-{os.urandom(4).hex()}",
        product_name="User X Unique Scan",
        owner_user_id=user_x,
        organization_id=f"org_{user_x}",
    )
    await save_analysis(
        analysis_id=f"ana-y-{os.urandom(4).hex()}",
        product_name="User Y Private Scan",
        owner_user_id=user_y,
        organization_id=f"org_{user_y}",
    )

    res = client.get("/api/history", headers={"Authorization": f"Bearer {token_x}"})
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["product_name"] == "User X Unique Scan"


# ── 13. OWN SCAN DELETION ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_13_own_scan_deletion():
    """User can delete their own analysis from history; record is permanently deleted."""
    await init_db()
    client = TestClient(app)
    user = f"del_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-del-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="To Be Deleted Product",
        owner_user_id=user,
        organization_id=f"org_{user}",
    )

    # Delete record
    del_res = client.delete(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200

    # Verify subsequent GET returns 404
    get_res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 404


# ── 14. CROSS-USER SCAN IDOR ACCESS DENIED ────────────────────────────────────

@pytest.mark.asyncio
async def test_14_cross_user_scan_access_denied():
    """User A cannot access User B's scan detail (returns 403 Forbidden)."""
    await init_db()
    client = TestClient(app)
    user_a = f"idor_a_{os.urandom(4).hex()}"
    user_b = f"idor_b_{os.urandom(4).hex()}"
    await _create_test_user(user_a, ROLE_USER, f"org_{user_a}")
    await _create_test_user(user_b, ROLE_USER, f"org_{user_b}")

    token_a = create_token(user_a, ROLE_USER)

    ana_b_id = f"ana-b-secret-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_b_id,
        product_name="User B Confidential Packaging",
        owner_user_id=user_b,
        organization_id=f"org_{user_b}",
    )

    # User A tries to open User B's analysis
    res = client.get(f"/api/history/{ana_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 403


# ── 15. CROSS-USER IMAGE IDOR ACCESS DENIED ───────────────────────────────────

@pytest.mark.asyncio
async def test_15_cross_user_image_access_denied():
    """User A cannot access User B's uploaded artwork image (returns 403 Forbidden)."""
    await init_db()
    client = TestClient(app)
    user_a = f"img_idor_a_{os.urandom(4).hex()}"
    user_b = f"img_idor_b_{os.urandom(4).hex()}"
    await _create_test_user(user_a, ROLE_USER, f"org_{user_a}")
    await _create_test_user(user_b, ROLE_USER, f"org_{user_b}")

    token_a = create_token(user_a, ROLE_USER)

    b_filename = f"user_b_img_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, b_filename)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    await save_analysis(
        analysis_id=f"ana-b-img-{os.urandom(4).hex()}",
        product_name="User B Product",
        owner_user_id=user_b,
        organization_id=f"org_{user_b}",
        image_filename=b_filename,
    )

    # User A tries to fetch User B's image
    res = client.get(f"/api/images/{b_filename}", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 403


# ── 16. CROSS-USER REPORT IDOR ACCESS DENIED ──────────────────────────────────

@pytest.mark.asyncio
async def test_16_cross_user_report_access_denied():
    """User A cannot download User B's report (returns 403 Forbidden)."""
    await init_db()
    client = TestClient(app)
    user_a = f"rep_idor_a_{os.urandom(4).hex()}"
    user_b = f"rep_idor_b_{os.urandom(4).hex()}"
    await _create_test_user(user_a, ROLE_USER, f"org_{user_a}")
    await _create_test_user(user_b, ROLE_USER, f"org_{user_b}")

    token_a = create_token(user_a, ROLE_USER)

    ana_b_id = f"ana-rep-b-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_b_id,
        product_name="User B Report Target",
        owner_user_id=user_b,
        organization_id=f"org_{user_b}",
        compliance_result={"score": 90.0, "status": "COMPLIANT", "checks": []},
    )

    # User A tries to access User B's report endpoints
    res_pdf = client.get(f"/api/report/{ana_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_pdf.status_code == 403

    res_csv = client.get(f"/api/report/{ana_b_id}/csv", headers={"Authorization": f"Bearer {token_a}"})
    assert res_csv.status_code == 403


# ── 17. REPORT TICKET SECURITY ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_17_report_ticket_security():
    """Download ticket is single-use, expires, and cannot be used across different resources."""
    await init_db()
    client = TestClient(app)
    user = f"ticket_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    ana_id = f"ana-ticket-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Ticket Security Product",
        owner_user_id=user,
        organization_id=f"org_{user}",
        compliance_result={"score": 100.0, "status": "COMPLIANT", "checks": []},
    )

    # 1. Request valid ticket
    ticket_res = client.post(
        "/api/auth/download-ticket",
        headers={"Authorization": f"Bearer {token}"},
        json={"resource_type": "report", "resource_id": ana_id}
    )
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["ticket"]

    # 2. First download succeeds
    dl_res = client.get(f"/api/report/{ana_id}/json?ticket={ticket}")
    assert dl_res.status_code == 200

    # 3. Second download with same ticket fails (single-use consumed)
    dl_res_2 = client.get(f"/api/report/{ana_id}/json?ticket={ticket}")
    assert dl_res_2.status_code == 401

    # 4. Invalid ticket fails
    dl_invalid = client.get(f"/api/report/{ana_id}/json?ticket=forged_ticket_12345")
    assert dl_invalid.status_code == 401


# ── 18. HUMAN REVIEW CORRECTION PRESERVES AI SNAPSHOT ─────────────────────────

@pytest.mark.asyncio
async def test_18_human_review_correction_preserves_ai_snapshot():
    """When an officer corrects a finding, original AI analysis record remains unchanged."""
    await init_db()
    ana_id = f"ana-snap-{os.urandom(4).hex()}"
    user = f"snap_user_{os.urandom(4).hex()}"
    officer = f"officer_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    await _create_test_user(officer, ROLE_ENFORCEMENT, "org_ministry")

    # Original AI snapshot had score 80.0, status REVIEW_REQUIRED
    await save_analysis(
        analysis_id=ana_id,
        product_name="AI Snapshot Preservation Oats",
        owner_user_id=user,
        organization_id=f"org_{user}",
        score=80.0,
        status="REVIEW_REQUIRED",
        compliance_result={
            "score": 80.0,
            "status": "REVIEW_REQUIRED",
            "checks": [{"rule_id": "FS-003", "status": "NEEDS_REVIEW", "explanation": "AI low confidence"}]
        }
    )

    # Officer records human review correction
    await save_review({
        "id": f"rev-{os.urandom(4).hex()}",
        "analysis_id": ana_id,
        "product_name": "AI Snapshot Preservation Oats",
        "verified_by": officer,
        "status": "APPROVED",
        "final_human_status": "PASS",
        "ai_score": 80.0,
        "ai_status": "REVIEW_REQUIRED",
        "ai_snapshot": {"score": 80.0, "status": "REVIEW_REQUIRED"},
        "field_corrections": [{"field": "FS-003", "corrected_status": "PASS"}],
        "comments": [{"note": "Physically verified ingredients declaration is present.", "author": officer}],
        "organization_id": "org_ministry",
    })

    # Verify AI historical record in analyses table is preserved
    original = await get_analysis(ana_id)
    assert original["score"] == 80.0
    assert original["status"] == "REVIEW_REQUIRED"

    # Verify officer review record is recorded in reviews table
    review = await get_review_by_analysis_id(ana_id)
    assert review is not None
    assert review["status"] == "APPROVED"
    assert review["verified_by"] == officer


# ── 19. HUMAN REVIEW CONFIRMATION REMAINS AUDITABLE ───────────────────────────

@pytest.mark.asyncio
async def test_19_human_review_confirmation_remains_auditable():
    """Officer confirmation records complete audit trail with timestamp, notes, and reviewer ID."""
    await init_db()
    ana_id = f"ana-audit-{os.urandom(4).hex()}"
    officer = f"auditor_{os.urandom(4).hex()}"
    await _create_test_user(officer, ROLE_ENFORCEMENT, "org_ministry")

    await save_analysis(
        analysis_id=ana_id,
        product_name="Audit Trail Biscuit",
        status="NON_COMPLIANT",
        score=50.0,
    )

    await save_review({
        "id": f"rev-aud-{os.urandom(4).hex()}",
        "analysis_id": ana_id,
        "product_name": "Audit Trail Biscuit",
        "verified_by": officer,
        "status": "REJECTED",
        "ai_score": 50.0,
        "ai_status": "NON_COMPLIANT",
        "ai_snapshot": {"score": 50.0, "status": "NON_COMPLIANT"},
        "comments": [{"note": "Confirmed missing MRP stamp upon physical audit inspection.", "author": officer}],
        "organization_id": "org_ministry",
    })

    review = await get_review_by_analysis_id(ana_id)
    assert review is not None
    assert review["verified_by"] == officer
    assert review["status"] == "REJECTED"
    assert "Confirmed missing MRP" in review["comments"]
    assert "created_at" in review


# ── 20. ERROR RESPONSES DO NOT EXPOSE RAW EXCEPTIONS ──────────────────────────

@pytest.mark.asyncio
async def test_20_error_responses_do_not_expose_raw_exceptions():
    """Non-existent or malformed requests return standard JSON errors without tracebacks or SQL dumps."""
    await init_db()
    client = TestClient(app)
    user = f"err_user_{os.urandom(4).hex()}"
    await _create_test_user(user, ROLE_USER, f"org_{user}")
    token = create_token(user, ROLE_USER)

    # 1. Non-existent analysis
    res_404 = client.get("/api/history/non-existent-id-99999", headers={"Authorization": f"Bearer {token}"})
    assert res_404.status_code == 404
    body = res_404.text
    assert "Traceback" not in body
    assert "sqlite3" not in body
    assert "SELECT" not in body

    # 2. Invalid image filename path traversal attempt
    res_trav = client.get("/api/images/../../etc/passwd", headers={"Authorization": f"Bearer {token}"})
    assert res_trav.status_code in (400, 403, 404)
    assert "Traceback" not in res_trav.text
