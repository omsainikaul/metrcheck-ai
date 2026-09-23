"""Phase 3C Test Suite: Merchant Integration + Security + Data Integrity QA.

Comprehensive forensic verification covering:
1. Product -> Scan Ownership & Linkage
2. Cross-Tenant Product Scan Injection Prevention
3. Malicious Ownership Injection Sanitization
4. Product -> Report Authorization (PDF, CSV, XLSX, JSON)
5. Product -> Image / Evidence File Security & IDOR
6. Product -> Artwork Authorization & Relational Linking
7. Pre-Print Compliance Workflow End-to-End
8. Version Comparison Tenant Isolation & Anti-Leakage
9. Product History Strict Scoping
10. Product Summary & Metric Accuracy (Zero Global Leakage)
11. Merchant Dashboard KPI Isolation
12. Product Search & Filter Isolation
13. Comprehensive IDOR & Fuzzing Protection
14. Archive Lifecycle & Historical Evidence Preservation
15. Hard Delete Safety & Evidence Immutability
16. Master Product Edit Immutability (Scans Do Not Mutate)
17. Historical Report Snapshot Integrity
18. Legacy Scan Compatibility (NULL/Empty product_id)
19. Normal User Workspace Isolation & Catalog Access Block
20. Officer Role Scoping & Non-Interference
21. Security & Lifecycle Audit Logging (PRODUCT_CREATED, UPDATED, ARCHIVED)
22. Concurrent Tenant Isolation (Zero Shared State Pollution)
"""

import pytest
import os
import io
import json
import asyncio
from fastapi.testclient import TestClient
from PIL import Image

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import (
    create_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
    ROLE_USER,
    hash_password
)
from database.db import (
    init_db,
    get_db,
    create_user,
    create_organization,
    create_product,
    get_product,
    update_product,
    archive_product,
    hard_delete_product,
    get_product_analyses,
    get_product_artworks,
    get_product_summary,
    get_merchant_dashboard_metrics,
    save_analysis,
    save_artwork,
    get_analysis
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


async def _seed_p3c_environment():
    """Ensure dedicated, collision-free test environment for Phase 3C."""
    await init_db()
    pwh, salt = hash_password("Password123!")

    # Organizations
    await create_organization("P3C_ORG_ALPHA", "Alpha Industries Ltd.", "MERCHANT")
    await create_organization("P3C_ORG_BETA", "Beta Packaged Goods Ltd.", "MERCHANT")
    await create_organization("P3C_GOV_ENFORCEMENT", "Legal Metrology Dept", "GOVERNMENT")
    await create_organization("P3C_GOV_AUDIT", "National Quality Council", "GOVERNMENT")

    # Users
    await create_user("p3c_merchant_alpha", pwh, salt, ROLE_MERCHANT, full_name="Alpha Merchant", organization_id="P3C_ORG_ALPHA")
    await create_user("p3c_merchant_beta", pwh, salt, ROLE_MERCHANT, full_name="Beta Merchant", organization_id="P3C_ORG_BETA")
    await create_user("p3c_normal_user", pwh, salt, ROLE_USER, full_name="Consumer Alex", organization_id="org_user_p3c_normal_user")
    await create_user("p3c_officer_enf", pwh, salt, ROLE_ENFORCEMENT, full_name="Officer Sharma", organization_id="P3C_GOV_ENFORCEMENT")
    await create_user("p3c_officer_audit", pwh, salt, ROLE_AUDIT, full_name="Inspector Roy", organization_id="P3C_GOV_AUDIT")
    await create_user("p3c_superadmin", pwh, salt, ROLE_ADMIN, full_name="Admin Director", organization_id="SYSTEM_ADMIN")


def _generate_test_image_bytes(color=(120, 180, 220)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (120, 120), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3C QA Test Cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_product_scan_ownership_and_linkage():
    """1. Product -> Scan Ownership: Server binds product_id and derives org/user from JWT."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    # 1. Create Product
    p_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Green Tea 250g", "brand_name": "AlphaOrganics", "mrp_declared": 299.0},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert p_res.status_code == 201
    prod_id = p_res.json()["id"]

    # 2. Run scan linked to Product
    scan_res = client.post(
        "/api/analyze/text",
        json={
            "text": "Alpha Green Tea 250g. MRP Rs. 299.00 incl. taxes. Net Qty 250 g. Mfg 01/2025. Mfd by Alpha Foods, Mumbai.",
            "product_id": prod_id
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert scan_res.status_code == 200
    scan_id = scan_res.json()["id"]

    # Verify directly in DB
    db_analysis = await get_analysis(scan_id)
    assert db_analysis is not None
    assert db_analysis["product_id"] == prod_id
    assert db_analysis["organization_id"] == "P3C_ORG_ALPHA"
    assert db_analysis["owner_user_id"] == "p3c_merchant_alpha"


@pytest.mark.asyncio
async def test_02_cross_tenant_product_scan_injection_blocked():
    """2. Cross-tenant product scan injection: Merchant A cannot attach a scan to Merchant B's product."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Merchant B creates product
    p_res_b = client.post(
        "/api/products",
        json={"product_name": "Beta Whey Protein 1kg", "brand_name": "BetaNutrition"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert p_res_b.status_code == 201
    prod_b_id = p_res_b.json()["id"]

    # Merchant A attempts to attach scan to Beta's product
    malicious_scan = client.post(
        "/api/analyze/text",
        json={
            "text": "Intruder Scan Text. MRP Rs. 500.",
            "product_id": prod_b_id
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert malicious_scan.status_code in [403, 404]


@pytest.mark.asyncio
async def test_03_malicious_ownership_injection_ignored():
    """3. Client-supplied organization_id / owner_user_id in analysis or product creation are ignored."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    # Attempt to spoof tenant during product creation
    p_res = client.post(
        "/api/products",
        json={
            "product_name": "Alpha Spoof Attempt Product",
            "organization_id": "P3C_ORG_BETA",
            "owner_user_id": "p3c_merchant_beta"
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert p_res.status_code == 201
    created_prod = p_res.json()
    assert created_prod["organization_id"] == "P3C_ORG_ALPHA"
    assert created_prod["owner_user_id"] == "p3c_merchant_alpha"


@pytest.mark.asyncio
async def test_04_product_report_authorization_all_formats():
    """4. Product -> Report Integration: Merchant A gets reports; Merchant B and Normal User are 403 denied."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    token_user = create_token("p3c_normal_user", ROLE_USER)
    client = TestClient(app)

    # 1. Product & Scan for Merchant A
    p_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Olive Oil 1L", "mrp_declared": 850.0},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    prod_id = p_res.json()["id"]

    scan_res = client.post(
        "/api/analyze/text",
        json={
            "text": "Alpha Olive Oil 1L. MRP Rs. 850.00. Net Qty 1 L. Mfg 01/2025. Mfd by Alpha Foods.",
            "product_id": prod_id
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    analysis_id = scan_res.json()["id"]

    # Merchant A can download all formats (PDF, CSV, XLSX, JSON)
    for fmt in ["pdf", "csv", "xlsx", "json"]:
        url = f"/api/report/{analysis_id}" if fmt == "pdf" else f"/api/report/{analysis_id}/{fmt}"
        res_a = client.get(url, headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200, f"Merchant A failed to download {fmt}: {res_a.text}"

    # Merchant B is blocked on all formats (403)
    for fmt in ["pdf", "csv", "xlsx", "json"]:
        url = f"/api/report/{analysis_id}" if fmt == "pdf" else f"/api/report/{analysis_id}/{fmt}"
        res_b = client.get(url, headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 403, f"Merchant B was not blocked on {fmt}!"

    # Normal User is blocked on all formats (403)
    for fmt in ["pdf", "csv", "xlsx", "json"]:
        url = f"/api/report/{analysis_id}" if fmt == "pdf" else f"/api/report/{analysis_id}/{fmt}"
        res_u = client.get(url, headers={"Authorization": f"Bearer {token_user}"})
        assert res_u.status_code == 403, f"Normal User was not blocked on {fmt}!"


@pytest.mark.asyncio
async def test_05_product_image_authorization_and_isolation():
    """5. Product -> Image Security: Uploaded evidence is strictly protected by tenant & ownership."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    token_user = create_token("p3c_normal_user", ROLE_USER)
    client = TestClient(app)

    # Save a mock analysis with image filename
    analysis_id = "p3c_img_test_analysis_01"
    filename = "p3c_product_alpha_label.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(_generate_test_image_bytes())

    await save_analysis({
        "id": analysis_id,
        "product_name": "Alpha Verified Pack",
        "image_filename": filename,
        "ocr_text": "Sample text",
        "extracted_data": {"product_name": "Alpha Verified Pack"},
        "compliance_result": {"status": "COMPLIANT", "compliance_score": 100.0, "checks": []},
        "score": 100.0,
        "status": "COMPLIANT",
        "owner_user_id": "p3c_merchant_alpha",
        "organization_id": "P3C_ORG_ALPHA"
    })

    # Merchant A can access image
    res_a = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200

    # Merchant B is denied (403/404)
    res_b = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code in [403, 404]

    # Normal User is denied (403/404)
    res_u = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token_user}"})
    assert res_u.status_code in [403, 404]


@pytest.mark.asyncio
async def test_06_product_artwork_authorization_and_linking():
    """6. Product -> Artwork: Artwork uploaded with product_id is linked and tenant-isolated."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    p_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Honey Jar 500g"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    prod_id = p_res.json()["id"]

    # Upload artwork
    img_bytes = _generate_test_image_bytes(color=(250, 200, 50))
    up_res = client.post(
        "/api/preprint/upload",
        files={"file": ("honey_dieline.png", io.BytesIO(img_bytes), "image/png")},
        data={"product_id": prod_id, "iteration_number": "1"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert up_res.status_code in (200, 201)
    artwork_id = up_res.json()["artwork_id"]

    # Merchant A sees artwork under product
    art_res_a = client.get(f"/api/products/{prod_id}/artworks", headers={"Authorization": f"Bearer {token_a}"})
    assert art_res_a.status_code == 200
    assert any(a["id"] == artwork_id for a in art_res_a.json()["artworks"])

    # Merchant B cannot view artworks for Merchant A's product
    art_res_b = client.get(f"/api/products/{prod_id}/artworks", headers={"Authorization": f"Bearer {token_b}"})
    assert art_res_b.status_code in [403, 404]


@pytest.mark.asyncio
async def test_07_preprint_workflow_end_to_end():
    """7. Pre-Print Workflow: Complete lifecycle from product to pre-print artwork inspection."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    p_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Organic Cashews 200g"},
        headers={"Authorization": f"Bearer {token}"}
    )
    prod_id = p_res.json()["id"]

    # Upload packaging artwork
    img_bytes = _generate_test_image_bytes(color=(180, 220, 100))
    up_res = client.post(
        "/api/preprint/upload",
        files={"file": ("cashew_pouch.png", io.BytesIO(img_bytes), "image/png")},
        data={"product_id": prod_id, "iteration_number": "1"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert up_res.status_code in (200, 201)
    artwork_id = up_res.json()["artwork_id"]

    # Fetch artwork detail via /api/preprint/{id}
    art_detail = client.get(f"/api/preprint/{artwork_id}", headers={"Authorization": f"Bearer {token}"})
    assert art_detail.status_code == 200
    data = art_detail.json()
    assert data["product_id"] == prod_id
    assert data["organization_id"] == "P3C_ORG_ALPHA"
    assert data["owner_user_id"] == "p3c_merchant_alpha"


@pytest.mark.asyncio
async def test_08_version_comparison_tenant_isolation():
    """8. Version Comparison: Merchant A compares own versions; cross-tenant comparison is 403 denied."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Merchant A artworks
    art_a1 = "art-p3c-alpha-v1"
    art_a2 = "art-p3c-alpha-v2"
    art_b1 = "art-p3c-beta-v1"

    await save_artwork({
        "id": art_a1, "filename": "alpha_v1.png", "file_path": "/tmp/a1.png", "file_type": "PNG",
        "file_size": 1000, "page_count": 1, "iteration_number": 1, "workflow_status": "DRAFT",
        "approval_status": "PENDING", "owner_user_id": "p3c_merchant_alpha", "organization_id": "P3C_ORG_ALPHA"
    })
    await save_artwork({
        "id": art_a2, "filename": "alpha_v2.png", "file_path": "/tmp/a2.png", "file_type": "PNG",
        "file_size": 1000, "page_count": 1, "iteration_number": 2, "workflow_status": "DRAFT",
        "approval_status": "PENDING", "owner_user_id": "p3c_merchant_alpha", "organization_id": "P3C_ORG_ALPHA"
    })
    await save_artwork({
        "id": art_b1, "filename": "beta_v1.png", "file_path": "/tmp/b1.png", "file_type": "PNG",
        "file_size": 1000, "page_count": 1, "iteration_number": 1, "workflow_status": "DRAFT",
        "approval_status": "PENDING", "owner_user_id": "p3c_merchant_beta", "organization_id": "P3C_ORG_BETA"
    })

    # Merchant A compares own versions -> 200 OK
    res_valid = client.post(
        "/api/versions/compare",
        json={"version_a_id": art_a1, "version_b_id": art_a2, "version_type_a": "ARTWORK", "version_type_b": "ARTWORK"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_valid.status_code == 200

    # Merchant A tries to compare own art_a1 with Merchant B's art_b1 -> 403 Forbidden
    res_cross = client.post(
        "/api/versions/compare",
        json={"version_a_id": art_a1, "version_b_id": art_b1, "version_type_a": "ARTWORK", "version_type_b": "ARTWORK"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_cross.status_code == 403


@pytest.mark.asyncio
async def test_09_product_history_strict_isolation():
    """9. Product History Isolation: Scans for Product A never appear in Product B history."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Create Product A and 2 scans
    p_a = client.post("/api/products", json={"product_name": "Alpha Oats 500g"}, headers={"Authorization": f"Bearer {token_a}"}).json()
    s_a1 = client.post("/api/analyze/text", json={"text": "Alpha Oats 500g. Scan 1. MRP Rs. 120. Net Qty 500g.", "product_id": p_a["id"]}, headers={"Authorization": f"Bearer {token_a}"}).json()
    s_a2 = client.post("/api/analyze/text", json={"text": "Alpha Oats 500g. Scan 2. MRP Rs. 120. Net Qty 500g.", "product_id": p_a["id"]}, headers={"Authorization": f"Bearer {token_a}"}).json()

    # Create Product B and 1 scan
    p_b = client.post("/api/products", json={"product_name": "Beta Rice 1kg"}, headers={"Authorization": f"Bearer {token_b}"}).json()
    s_b1 = client.post("/api/analyze/text", json={"text": "Beta Rice 1kg. Scan 1. MRP Rs. 80. Net Qty 1kg.", "product_id": p_b["id"]}, headers={"Authorization": f"Bearer {token_b}"}).json()

    # Check history A
    hist_a = client.get(f"/api/products/{p_a['id']}/history", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert hist_a["total"] == 2
    a_ids = [a["id"] for a in hist_a["analyses"]]
    assert s_a1["id"] in a_ids
    assert s_a2["id"] in a_ids
    assert s_b1["id"] not in a_ids

    # Check history B
    hist_b = client.get(f"/api/products/{p_b['id']}/history", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert hist_b["total"] == 1
    b_ids = [b["id"] for b in hist_b["analyses"]]
    assert s_b1["id"] in b_ids
    assert s_a1["id"] not in b_ids
    assert s_a2["id"] not in b_ids


@pytest.mark.asyncio
async def test_10_product_summary_tenant_and_metric_accuracy():
    """10. Product Summary: Metrics reflect only product-owned data without global aggregation."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    p_a = client.post("/api/products", json={"product_name": "Alpha Soy Milk 1L"}, headers={"Authorization": f"Bearer {token_a}"}).json()
    p_b = client.post("/api/products", json={"product_name": "Beta Coconut Milk 1L"}, headers={"Authorization": f"Bearer {token_b}"}).json()

    # Alpha gets 2 scans
    client.post("/api/analyze/text", json={"text": "Alpha Soy Milk. Scan 1. MRP Rs. 100. Net Qty 1L.", "product_id": p_a["id"]}, headers={"Authorization": f"Bearer {token_a}"})
    client.post("/api/analyze/text", json={"text": "Alpha Soy Milk. Scan 2. MRP Rs. 100. Net Qty 1L.", "product_id": p_a["id"]}, headers={"Authorization": f"Bearer {token_a}"})

    # Beta gets 4 scans
    for i in range(4):
        client.post("/api/analyze/text", json={"text": f"Beta Coconut Milk. Scan {i}. MRP Rs. 150. Net Qty 1L.", "product_id": p_b["id"]}, headers={"Authorization": f"Bearer {token_b}"})

    # Summary A must report exactly 2 scans (not 6)
    sum_a = client.get(f"/api/products/{p_a['id']}/summary", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert sum_a["total_scans"] == 2

    # Summary B must report exactly 4 scans
    sum_b = client.get(f"/api/products/{p_b['id']}/summary", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert sum_b["total_scans"] == 4


@pytest.mark.asyncio
async def test_11_merchant_dashboard_kpi_isolation():
    """11. Dashboard KPI stats: GET /api/products/stats strictly isolates tenant metrics."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    stats_a_before = client.get("/api/products/stats", headers={"Authorization": f"Bearer {token_a}"}).json()
    stats_b_before = client.get("/api/products/stats", headers={"Authorization": f"Bearer {token_b}"}).json()

    # Alpha creates 2 products
    client.post("/api/products", json={"product_name": "Alpha SKU X1"}, headers={"Authorization": f"Bearer {token_a}"})
    client.post("/api/products", json={"product_name": "Alpha SKU X2"}, headers={"Authorization": f"Bearer {token_a}"})

    # Beta creates 5 products
    for i in range(5):
        client.post("/api/products", json={"product_name": f"Beta SKU Y{i}"}, headers={"Authorization": f"Bearer {token_b}"})

    stats_a_after = client.get("/api/products/stats", headers={"Authorization": f"Bearer {token_a}"}).json()
    stats_b_after = client.get("/api/products/stats", headers={"Authorization": f"Bearer {token_b}"}).json()

    # Exact delta verification
    assert stats_a_after["active_products"] - stats_a_before["active_products"] == 2
    assert stats_b_after["active_products"] - stats_b_before["active_products"] == 5


@pytest.mark.asyncio
async def test_12_product_search_and_filter_isolation():
    """12. Product Search & Filter: Merchant A cannot discover Merchant B products."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Beta registers specific SKU
    client.post(
        "/api/products",
        json={"product_name": "Beta Unique Secret Formula 100ml", "brand_name": "SecretBetaBrand", "gtin_barcode": "8909999888877"},
        headers={"Authorization": f"Bearer {token_b}"}
    )

    # Merchant A searches for Beta's exact name, brand, and GTIN
    for q in ["Unique Secret", "SecretBetaBrand", "8909999888877"]:
        res = client.get(f"/api/products?q={q}", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        assert len(res.json()["products"]) == 0, f"Merchant A discovered Beta product with query '{q}'!"


@pytest.mark.asyncio
async def test_13_product_idor_fuzzing():
    """13. IDOR Fuzzing: Foreign UUIDs, random UUIDs, and malformed strings are blocked safely."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Merchant B creates product
    p_b = client.post("/api/products", json={"product_name": "Beta Protected SKU"}, headers={"Authorization": f"Bearer {token_b}"}).json()
    foreign_id = p_b["id"]

    test_ids = [
        foreign_id,
        "00000000-0000-0000-0000-000000000000",
        "../../etc/passwd",
        "non_existent_id_123",
        "' OR '1'='1"
    ]

    for tid in test_ids:
        # GET detail
        r1 = client.get(f"/api/products/{tid}", headers={"Authorization": f"Bearer {token_a}"})
        assert r1.status_code in [400, 403, 404]

        # PATCH
        r2 = client.patch(f"/api/products/{tid}", json={"product_name": "Hacked"}, headers={"Authorization": f"Bearer {token_a}"})
        assert r2.status_code in [400, 403, 404]

        # DELETE
        r3 = client.delete(f"/api/products/{tid}", headers={"Authorization": f"Bearer {token_a}"})
        assert r3.status_code in [400, 403, 404]


@pytest.mark.asyncio
async def test_14_archive_preserves_historical_scans_and_artworks():
    """14. Archive Lifecycle: Soft-archived product preserves all historical scans and artworks."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    p_res = client.post("/api/products", json={"product_name": "Alpha Seasonal Cider 500ml"}, headers={"Authorization": f"Bearer {token}"})
    prod_id = p_res.json()["id"]

    # Link scan
    scan_res = client.post("/api/analyze/text", json={"text": "Alpha Seasonal Cider 500ml. MRP Rs. 150.", "product_id": prod_id}, headers={"Authorization": f"Bearer {token}"})
    analysis_id = scan_res.json()["id"]

    # Archive product
    del_res = client.delete(f"/api/products/{prod_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "ARCHIVED"

    # Historical scan remains linked and valid
    analysis = await get_analysis(analysis_id)
    assert analysis is not None
    assert analysis["product_id"] == prod_id

    # Scan history endpoint still returns the analysis
    hist = client.get(f"/api/products/{prod_id}/history", headers={"Authorization": f"Bearer {token}"})
    assert hist.status_code == 200
    assert len(hist.json()["analyses"]) == 1


@pytest.mark.asyncio
async def test_15_hard_delete_preserves_historical_analyses_and_evidence():
    """15. Hard Delete Safety: Permanent SKU removal never cascades or destroys historical analyses."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    p_res = client.post("/api/products", json={"product_name": "Alpha Discontinued Prototype"}, headers={"Authorization": f"Bearer {token}"})
    prod_id = p_res.json()["id"]

    # Link scan
    scan_res = client.post("/api/analyze/text", json={"text": "Alpha Prototype Scan. MRP Rs. 99.", "product_id": prod_id}, headers={"Authorization": f"Bearer {token}"})
    analysis_id = scan_res.json()["id"]

    # Hard delete product record
    hard_del = client.delete(f"/api/products/{prod_id}?hard_delete=true", headers={"Authorization": f"Bearer {token}"})
    assert hard_del.status_code == 200

    # Product record is gone
    assert (await get_product(prod_id)) is None

    # Analysis record is still completely intact in database
    analysis = await get_analysis(analysis_id)
    assert analysis is not None
    assert analysis["id"] == analysis_id
    assert analysis["score"] is not None


@pytest.mark.asyncio
async def test_16_master_product_edit_does_not_mutate_historical_scans():
    """16. Data Immutability: Editing master product declared MRP does not alter past scan evidence."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    # 1. Create Product with declared MRP Rs. 100
    p_res = client.post("/api/products", json={"product_name": "Alpha Almond Butter 200g", "mrp_declared": 100.0}, headers={"Authorization": f"Bearer {token}"})
    prod_id = p_res.json()["id"]

    # 2. Run scan recording MRP Rs. 100
    scan_res = client.post("/api/analyze/text", json={"text": "Alpha Almond Butter 200g. MRP Rs. 100.00. Net Qty 200g.", "product_id": prod_id}, headers={"Authorization": f"Bearer {token}"})
    analysis_id = scan_res.json()["id"]

    # 3. Merchant updates Master SKU MRP to Rs. 150
    patch_res = client.patch(f"/api/products/{prod_id}", json={"mrp_declared": 150.0}, headers={"Authorization": f"Bearer {token}"})
    assert patch_res.status_code == 200
    assert patch_res.json()["mrp_declared"] == 150.0

    # 4. Verify historical scan record still contains the original scan evidence
    analysis = await get_analysis(analysis_id)
    assert "MRP Rs. 100.00" in analysis["ocr_text"]


@pytest.mark.asyncio
async def test_17_historical_report_snapshot_integrity():
    """17. Report Snapshot Integrity: Reports reflect immutable analysis record."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    p_res = client.post("/api/products", json={"product_name": "Alpha Coconut Oil 500ml", "mrp_declared": 200.0}, headers={"Authorization": f"Bearer {token}"})
    prod_id = p_res.json()["id"]

    # Directly save analysis with structured product metadata
    analysis_id = "p3c_report_integrity_analysis_01"
    await save_analysis({
        "id": analysis_id,
        "product_name": "Alpha Coconut Oil 500ml",
        "image_filename": "coconut_oil.jpg",
        "ocr_text": "Product Name: Alpha Coconut Oil 500ml\nMRP: Rs. 200.00\nNet Qty: 500 ml",
        "extracted_data": {
            "product_name": "Alpha Coconut Oil 500ml",
            "mrp": "200.0",
            "net_quantity": "500 ml"
        },
        "compliance_result": {
            "status": "COMPLIANT",
            "compliance_score": 95.0,
            "checks": [],
            "product_info": {
                "product_name": "Alpha Coconut Oil 500ml",
                "mrp": "200.0",
                "net_quantity": "500 ml"
            }
        },
        "score": 95.0,
        "status": "COMPLIANT",
        "owner_user_id": "p3c_merchant_alpha",
        "organization_id": "P3C_ORG_ALPHA",
        "product_id": prod_id
    })

    # JSON report check
    rep_json = client.get(f"/api/report/{analysis_id}/json", headers={"Authorization": f"Bearer {token}"}).json()
    assert rep_json["product_name"] == "Alpha Coconut Oil 500ml"

    # CSV report check
    rep_csv = client.get(f"/api/report/{analysis_id}/csv", headers={"Authorization": f"Bearer {token}"})
    assert rep_csv.status_code == 200
    assert "Alpha Coconut Oil 500ml" in rep_csv.text


@pytest.mark.asyncio
async def test_18_legacy_record_compatibility_without_product_id():
    """18. Legacy Compatibility: Standalone analyses without product_id function across all endpoints."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    # Create scan without product_id
    scan_res = client.post(
        "/api/analyze/text",
        json={"text": "Standalone Legacy Package. MRP Rs. 45. Net Qty 100g. Mfg 02/2025."},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert scan_res.status_code == 200
    analysis_id = scan_res.json()["id"]

    # History list
    hist_res = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert hist_res.status_code == 200

    # Detail
    det_res = client.get(f"/api/history/{analysis_id}", headers={"Authorization": f"Bearer {token}"})
    assert det_res.status_code == 200

    # Report
    rep_res = client.get(f"/api/report/{analysis_id}/json", headers={"Authorization": f"Bearer {token}"})
    assert rep_res.status_code == 200


@pytest.mark.asyncio
async def test_19_normal_user_isolation_and_catalog_access_block():
    """19. Normal User Boundary: Consumer can check products & view personal history, but is blocked from catalog."""
    await _seed_p3c_environment()
    token_user = create_token("p3c_normal_user", ROLE_USER)
    client = TestClient(app)

    # Normal user runs consumer scan -> 200 OK
    scan_res = client.post(
        "/api/analyze/text",
        json={"text": "Consumer Verified Soap. MRP Rs. 35. Net Qty 75g."},
        headers={"Authorization": f"Bearer {token_user}"}
    )
    assert scan_res.status_code == 200

    # Normal user attempts to access /api/products -> 403 Forbidden
    catalog_res = client.get("/api/products", headers={"Authorization": f"Bearer {token_user}"})
    assert catalog_res.status_code == 403

    # Normal user attempts to create product -> 403 Forbidden
    create_res = client.post("/api/products", json={"product_name": "Consumer Fake Product"}, headers={"Authorization": f"Bearer {token_user}"})
    assert create_res.status_code == 403

    # Normal user attempts to access merchant stats -> 403 Forbidden
    stats_res = client.get("/api/products/stats", headers={"Authorization": f"Bearer {token_user}"})
    assert stats_res.status_code == 403


@pytest.mark.asyncio
async def test_20_officer_role_scoping_and_non_interference():
    """20. Officer Scoping: Officers cannot manage merchant products, preserving role segregation."""
    await _seed_p3c_environment()
    token_enf = create_token("p3c_officer_enf", ROLE_ENFORCEMENT)
    token_audit = create_token("p3c_officer_audit", ROLE_AUDIT)
    client = TestClient(app)

    # Enforcement Officer cannot create merchant product -> 403 Forbidden
    r1 = client.post("/api/products", json={"product_name": "Officer Prohibited Product"}, headers={"Authorization": f"Bearer {token_enf}"})
    assert r1.status_code == 403

    # Audit Officer cannot create merchant product -> 403 Forbidden
    r2 = client.post("/api/products", json={"product_name": "Audit Prohibited Product"}, headers={"Authorization": f"Bearer {token_audit}"})
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_21_audit_logging_of_product_lifecycle():
    """21. Audit Logging: PRODUCT_CREATED, PRODUCT_UPDATED, PRODUCT_ARCHIVED are recorded."""
    await _seed_p3c_environment()
    token = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    # 1. Create
    p_res = client.post("/api/products", json={"product_name": "Alpha Audit Log Test SKU"}, headers={"Authorization": f"Bearer {token}"})
    prod_id = p_res.json()["id"]

    # 2. Update
    client.patch(f"/api/products/{prod_id}", json={"brand_name": "AlphaAuditBrand"}, headers={"Authorization": f"Bearer {token}"})

    # 3. Archive
    client.delete(f"/api/products/{prod_id}", headers={"Authorization": f"Bearer {token}"})

    # Verify audit logs in database
    db = await get_db()
    try:
        cursor = await db.execute("SELECT event_type FROM account_audit_logs WHERE actor_username = 'p3c_merchant_alpha'")
        rows = await cursor.fetchall()
        events = [r[0] for r in rows]
        assert "PRODUCT_CREATED" in events
        assert "PRODUCT_UPDATED" in events
        assert "PRODUCT_ARCHIVED" in events
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_22_concurrent_tenant_isolation():
    """22. Concurrency: Simultaneous requests from Merchant A and Merchant B do not pollute state."""
    await _seed_p3c_environment()
    token_a = create_token("p3c_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3c_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Create distinct products for each
    p_a = client.post("/api/products", json={"product_name": "Concurrent Alpha Product"}, headers={"Authorization": f"Bearer {token_a}"}).json()
    p_b = client.post("/api/products", json={"product_name": "Concurrent Beta Product"}, headers={"Authorization": f"Bearer {token_b}"}).json()

    async def fetch_a():
        return client.get(f"/api/products/{p_a['id']}", headers={"Authorization": f"Bearer {token_a}"})

    async def fetch_b():
        return client.get(f"/api/products/{p_b['id']}", headers={"Authorization": f"Bearer {token_b}"})

    results = await asyncio.gather(fetch_a(), fetch_b(), fetch_a(), fetch_b())
    assert results[0].status_code == 200 and results[0].json()["product_name"] == "Concurrent Alpha Product"
    assert results[1].status_code == 200 and results[1].json()["product_name"] == "Concurrent Beta Product"
    assert results[2].status_code == 200 and results[2].json()["product_name"] == "Concurrent Alpha Product"
    assert results[3].status_code == 200 and results[3].json()["product_name"] == "Concurrent Beta Product"
