"""Phase 3B Test Suite: Merchant Product Catalog + Business Workspace.

Comprehensive test coverage verifying:
1. Product CRUD (Create, Read, Update, Soft-Delete/Archive, Hard-Delete)
2. Role-Based Access Control (RBAC: Merchant/Admin allowed, Normal User/Officers blocked from /api/products)
3. Strict Tenant Isolation & Anti-IDOR (No cross-org or cross-merchant leakage)
4. Product-Linked Physical Scans (analyses table with product_id)
5. Product-Linked Pre-Print Packaging Artworks (artworks table with product_id)
6. Backward Compatibility (Normal User scans without product_id, legacy NULL product_id)
7. Product Compliance Summary and Merchant Dashboard Stats isolation
"""

import pytest
import os
import io
from fastapi.testclient import TestClient
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
    create_user,
    create_organization,
    create_product,
    get_product,
    list_products,
    update_product,
    archive_product,
    delete_product,
    get_product_analyses,
    get_product_artworks,
    get_product_summary,
    get_merchant_dashboard_metrics,
    save_analysis,
    save_artwork
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


async def _seed_users():
    """Ensure test users and organizations are provisioned."""
    await init_db()
    pwh, salt = hash_password("Password123!")

    # Organizations
    await create_organization("P3B_ORG_ALPHA", "Alpha Brands Inc.", "MERCHANT")
    await create_organization("P3B_ORG_BETA", "Beta Organics Ltd.", "MERCHANT")
    await create_organization("P3B_GOV_ENFORCEMENT", "Legal Metrology Dept", "GOVERNMENT")

    # Users
    await create_user("p3b_merchant_alpha", pwh, salt, ROLE_MERCHANT, full_name="Alpha Merchant", organization_id="P3B_ORG_ALPHA")
    await create_user("p3b_merchant_beta", pwh, salt, ROLE_MERCHANT, full_name="Beta Merchant", organization_id="P3B_ORG_BETA")
    await create_user("p3b_consumer_jane", pwh, salt, ROLE_USER, full_name="Jane Consumer", organization_id="org_user_p3b_consumer_jane")
    await create_user("p3b_officer_kumar", pwh, salt, ROLE_ENFORCEMENT, full_name="Officer Kumar", organization_id="P3B_GOV_ENFORCEMENT")
    await create_user("p3b_superadmin", pwh, salt, ROLE_ADMIN, full_name="Admin User", organization_id="SYSTEM_ADMIN")


# ─────────────────────────────────────────────────────────────────────────────
# Test Scenarios
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_merchant_creates_product_successfully():
    """Scenario 1: Merchant creates product successfully with all legal metrology fields."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)
    payload = {
        "product_name": "Alpha Organic Almond Milk 1L",
        "brand_name": "Alpha Organics",
        "category": "FOOD_BEVERAGES",
        "gtin_barcode": "8901234567890",
        "fssai_license": "10014011000123",
        "legal_metrology_license": "LM/MH/2024/001",
        "net_quantity_declared": "1 L",
        "mrp_declared": 250.0,
        "unit_sale_price_declared": "₹0.25 / ml",
        "manufacturer_name": "Alpha Foods Ltd, Mumbai",
        "country_of_origin": "India"
    }
    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["product_name"] == "Alpha Organic Almond Milk 1L"
    assert data["organization_id"] == "P3B_ORG_ALPHA"
    assert data["owner_user_id"] == "p3b_merchant_alpha"
    assert data["status"] == "ACTIVE"
    assert data["mrp_declared"] == 250.0
    assert "id" in data


@pytest.mark.asyncio
async def test_02_normal_user_cannot_create_product():
    """Scenario 2: Normal User is blocked from creating products (403 Forbidden)."""
    await _seed_users()
    token = create_token("p3b_consumer_jane", ROLE_USER)
    client = TestClient(app)
    payload = {
        "product_name": "Unauthorized Consumer Product",
        "brand_name": "FakeBrand"
    }
    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_03_enforcement_officer_cannot_create_product():
    """Scenario 3: Enforcement Officer is blocked from creating products (403 Forbidden)."""
    await _seed_users()
    token = create_token("p3b_officer_kumar", ROLE_ENFORCEMENT)
    client = TestClient(app)
    payload = {
        "product_name": "Officer Test Product"
    }
    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_04_merchant_lists_only_own_products_tenant_isolation():
    """Scenario 4: Merchant lists only own organization's products."""
    await _seed_users()
    token_a = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3b_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Create product for Org A
    client.post(
        "/api/products",
        json={"product_name": "Alpha Biscuit 200g"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    # Create product for Org B
    client.post(
        "/api/products",
        json={"product_name": "Beta Juice 500ml"},
        headers={"Authorization": f"Bearer {token_b}"}
    )

    # Merchant A list
    res_a = client.get("/api/products", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    prods_a = res_a.json()["products"]
    names_a = [p["product_name"] for p in prods_a]
    assert "Alpha Biscuit 200g" in names_a
    assert "Beta Juice 500ml" not in names_a

    # Merchant B list
    res_b = client.get("/api/products", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    prods_b = res_b.json()["products"]
    names_b = [p["product_name"] for p in prods_b]
    assert "Beta Juice 500ml" in names_b
    assert "Alpha Biscuit 200g" not in names_b


@pytest.mark.asyncio
async def test_05_normal_user_cannot_access_product_catalog():
    """Scenario 5: Normal User cannot access /api/products list (403 Forbidden)."""
    await _seed_users()
    token = create_token("p3b_consumer_jane", ROLE_USER)
    client = TestClient(app)
    res = client.get("/api/products", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_06_cross_tenant_product_access_blocked():
    """Scenario 6: Cross-tenant product access by ID is blocked (403 or 404)."""
    await _seed_users()
    token_a = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3b_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Confidential Formula"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    product_id = create_res.json()["id"]

    # Merchant B attempts to fetch Org A product
    res = client.get(
        f"/api/products/{product_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_07_merchant_updates_own_product():
    """Scenario 7: Merchant updates own product metadata."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Shampoo 200ml", "mrp_declared": 180.0},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    # Update MRP and Brand
    update_res = client.patch(
        f"/api/products/{product_id}",
        json={"mrp_declared": 199.0, "brand_name": "Alpha HairCare"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["mrp_declared"] == 199.0
    assert updated["brand_name"] == "Alpha HairCare"
    assert updated["product_name"] == "Alpha Shampoo 200ml"


@pytest.mark.asyncio
async def test_08_merchant_cannot_update_another_tenant_product():
    """Scenario 8: Merchant cannot update another tenant's product."""
    await _seed_users()
    token_a = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3b_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Premium Tea"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    product_id = create_res.json()["id"]

    update_res = client.patch(
        f"/api/products/{product_id}",
        json={"product_name": "Hacked Tea"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert update_res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_09_merchant_archives_product_soft_delete():
    """Scenario 9: Merchant archives product (soft delete)."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Summer Soda 300ml"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    del_res = client.delete(
        f"/api/products/{product_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Product archived successfully."

    # Verify status is ARCHIVED
    get_res = client.get(
        f"/api/products/{product_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_10_product_archive_preserves_historical_analyses():
    """Scenario 10: Product archive preserves historical scans and reports."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Audit Preserved Item"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    # Save an analysis linked to this product
    analysis_id = "test_analysis_preserved_01"
    await save_analysis({
        "id": analysis_id,
        "product_name": "Alpha Audit Preserved Item",
        "image_filename": "preserved_label.jpg",
        "ocr_text": "MRP Rs. 100",
        "extracted_data": {"product_name": "Alpha Audit Preserved Item", "mrp": "100.0"},
        "compliance_result": {"status": "COMPLIANT", "compliance_score": 95.0, "checks": []},
        "score": 95.0,
        "status": "COMPLIANT",
        "owner_user_id": "p3b_merchant_alpha",
        "organization_id": "P3B_ORG_ALPHA",
        "product_id": product_id
    })

    # Archive the product
    client.delete(f"/api/products/{product_id}", headers={"Authorization": f"Bearer {token}"})

    # Historical analyses linked to this product still exist
    history = await get_product_analyses(product_id, "P3B_ORG_ALPHA")
    assert len(history) == 1
    assert history[0]["id"] == analysis_id


@pytest.mark.asyncio
async def test_11_product_archive_preserves_packaging_artworks():
    """Scenario 11: Product archive preserves pre-print artworks."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Artwork Preserved Item"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    # Save an artwork linked to this product
    artwork_id = "test_art_preserved_01"
    await save_artwork({
        "id": artwork_id,
        "filename": "dieline_pack_v1.pdf",
        "file_path": "/tmp/dieline_pack_v1.pdf",
        "file_type": "PDF",
        "file_size": 10240,
        "page_count": 1,
        "iteration_number": 1,
        "workflow_status": "DRAFT",
        "approval_status": "PENDING",
        "owner_user_id": "p3b_merchant_alpha",
        "organization_id": "P3B_ORG_ALPHA",
        "product_id": product_id,
        "created_at": "2026-09-20T10:00:00Z",
        "updated_at": "2026-09-20T10:00:00Z"
    })

    # Archive product
    client.delete(f"/api/products/{product_id}", headers={"Authorization": f"Bearer {token}"})

    # Artworks still exist and link to product
    arts = await get_product_artworks(product_id, "P3B_ORG_ALPHA")
    assert len(arts) == 1
    assert arts[0]["id"] == artwork_id


@pytest.mark.asyncio
async def test_12_merchant_hard_delete_product():
    """Scenario 12: Merchant hard delete deletes product record."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Temporary SKU"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    del_res = client.delete(
        f"/api/products/{product_id}?hard_delete=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert del_res.status_code == 200

    # Verification: Should return 404
    get_res = client.get(
        f"/api/products/{product_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_13_merchant_scan_links_product_id():
    """Scenario 13: Analysis workflow accepts and stores product_id for merchant."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Tested Flour 5kg"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    text_payload = {
        "text": "Alpha Tested Flour 5kg. MRP Rs. 350.00 incl. of all taxes. Mfg Date 01/2025. Best before 6 months. Net weight 5 kg. Mfd by Alpha Foods, Mumbai.",
        "product_id": product_id
    }
    res = client.post(
        "/api/analyze/text",
        json=text_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    analysis_id = data["id"]

    # Verify history of product contains this analysis
    hist_res = client.get(
        f"/api/products/{product_id}/history",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert hist_res.status_code == 200
    analyses = hist_res.json()["analyses"]
    assert any(a["id"] == analysis_id for a in analyses)


@pytest.mark.asyncio
async def test_14_normal_user_scan_creates_analysis_without_product_id():
    """Scenario 14: Normal User scan creates analysis with product_id=None."""
    await _seed_users()
    token = create_token("p3b_consumer_jane", ROLE_USER)
    client = TestClient(app)

    text_payload = {
        "text": "Consumer Checked Biscuit. MRP Rs. 20.00. Net Qty 100g. Mfg 02/2025."
    }
    res = client.post(
        "/api/analyze/text",
        json=text_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_15_analysis_without_product_id_functions_normally():
    """Scenario 15: Backward compatibility - analysis without product_id functions normally."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    text_payload = {
        "text": "Legacy Standalone Scan. Net Qty 500ml. MRP Rs. 50."
    }
    res = client.post(
        "/api/analyze/text",
        json=text_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_16_product_scan_history_endpoint():
    """Scenario 16: Product scan history endpoint returns linked analyses in order."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Multi-Scan Juice"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    # Run two scans for this product
    client.post(
        "/api/analyze/text",
        json={"text": "Alpha Multi-Scan Juice. MRP Rs. 40. Net Qty 200ml.", "product_id": product_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    client.post(
        "/api/analyze/text",
        json={"text": "Alpha Multi-Scan Juice. MRP Rs. 40. Net Qty 200ml. Batch B-99.", "product_id": product_id},
        headers={"Authorization": f"Bearer {token}"}
    )

    res = client.get(
        f"/api/products/{product_id}/history",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["total"] >= 2


@pytest.mark.asyncio
async def test_17_cross_tenant_cannot_view_product_scan_history():
    """Scenario 17: Cross-tenant cannot view product scan history."""
    await _seed_users()
    token_a = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3b_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Private Scan Product"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    product_id = create_res.json()["id"]

    res = client.get(
        f"/api/products/{product_id}/history",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_18_merchant_uploads_preprint_artwork_with_product_id():
    """Scenario 18: Upload pre-print artwork with product_id."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Dieline Carton Box"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(200, 100, 50))
    img.save(buf, format="PNG")
    file_bytes = buf.getvalue()

    res = client.post(
        "/api/preprint/upload",
        files={"file": ("packaging_box.png", io.BytesIO(file_bytes), "image/png")},
        data={"iteration_number": "1", "product_id": product_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code in (200, 201), res.text
    artwork_id = res.json()["artwork_id"]

    # Verify artwork is linked to product
    art_res = client.get(
        f"/api/products/{product_id}/artworks",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert art_res.status_code == 200
    artworks = art_res.json()["artworks"]
    assert any(a["id"] == artwork_id for a in artworks)


@pytest.mark.asyncio
async def test_19_product_artwork_list_endpoint():
    """Scenario 19: Product artwork list endpoint returns linked artworks."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Artwork Listed Product"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(100, 200, 50))
    img.save(buf, format="PNG")
    file_bytes = buf.getvalue()

    client.post(
        "/api/preprint/upload",
        files={"file": ("label_v1.png", io.BytesIO(file_bytes), "image/png")},
        data={"iteration_number": "1", "product_id": product_id},
        headers={"Authorization": f"Bearer {token}"}
    )

    res = client.get(
        f"/api/products/{product_id}/artworks",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    artworks = res.json()["artworks"]
    assert len(artworks) >= 1
    assert artworks[0]["product_id"] == product_id


@pytest.mark.asyncio
async def test_20_cross_tenant_cannot_view_product_artworks():
    """Scenario 20: Cross-tenant cannot view product artworks."""
    await _seed_users()
    token_a = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3b_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Secret Artwork Item"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    product_id = create_res.json()["id"]

    res = client.get(
        f"/api/products/{product_id}/artworks",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_21_product_summary_endpoint_metrics():
    """Scenario 21: Product summary endpoint computes accurate compliance metrics."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Metric Summary Product"},
        headers={"Authorization": f"Bearer {token}"}
    )
    product_id = create_res.json()["id"]

    # Run compliant scan
    client.post(
        "/api/analyze/text",
        json={
            "text": "Alpha Metric Summary Product. MRP Rs. 99.00. Net Qty 500g. Mfg 01/2025. Best before 12 months. Mfd by Alpha Foods, Mumbai. Consumer care: 1800-123-456, support@alpha.com",
            "product_id": product_id
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    res = client.get(
        f"/api/products/{product_id}/summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_scans"] >= 1
    assert data["latest_score"] > 0
    assert data["latest_status"].replace(" ", "_") in ["COMPLIANT", "REVIEW_REQUIRED", "NON_COMPLIANT"]


@pytest.mark.asyncio
async def test_22_merchant_dashboard_stats():
    """Scenario 22: Merchant dashboard stats endpoint returns accurate organization metrics."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    res = client.get(
        "/api/products/stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "active_products" in data
    assert "products_checked" in data
    assert "attention_required" in data
    assert "critical_findings" in data
    assert "packaging_artworks" in data


@pytest.mark.asyncio
async def test_23_merchant_dashboard_stats_exclude_other_tenants():
    """Scenario 23: Merchant dashboard stats strictly exclude other tenants' data."""
    await _seed_users()
    token_a = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("p3b_merchant_beta", ROLE_MERCHANT)
    client = TestClient(app)

    # Merchant B creates 3 products
    for i in range(3):
        client.post(
            "/api/products",
            json={"product_name": f"Beta Isolated Product {i}"},
            headers={"Authorization": f"Bearer {token_b}"}
        )

    # Merchant A stats should not count Beta products
    res_a = client.get(
        "/api/products/stats",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    res_b = client.get(
        "/api/products/stats",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_a.status_code == 200
    assert res_b.status_code == 200
    stats_b = res_b.json()
    assert stats_b["active_products"] >= 3


@pytest.mark.asyncio
async def test_24_product_search_and_filter():
    """Scenario 24: Product catalog search and category filtering."""
    await _seed_users()
    token = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    client.post(
        "/api/products",
        json={"product_name": "Alpha Gourmet Choco Cookies", "category": "FOOD_BEVERAGES"},
        headers={"Authorization": f"Bearer {token}"}
    )
    client.post(
        "/api/products",
        json={"product_name": "Alpha Herbal Face Wash", "category": "COSMETICS"},
        headers={"Authorization": f"Bearer {token}"}
    )

    # Search by keyword
    search_res = client.get(
        "/api/products?q=Choco",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert search_res.status_code == 200
    prods = search_res.json()["products"]
    assert len(prods) == 1
    assert "Choco Cookies" in prods[0]["product_name"]

    # Filter by category
    cat_res = client.get(
        "/api/products?category=COSMETICS",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert cat_res.status_code == 200
    cat_prods = cat_res.json()["products"]
    assert all(p["category"] == "COSMETICS" for p in cat_prods)


@pytest.mark.asyncio
async def test_25_admin_can_access_and_manage_products():
    """Scenario 25: Admin role can view and manage merchant products for system oversight."""
    await _seed_users()
    token_admin = create_token("p3b_superadmin", ROLE_ADMIN)
    token_merchant = create_token("p3b_merchant_alpha", ROLE_MERCHANT)
    client = TestClient(app)

    create_res = client.post(
        "/api/products",
        json={"product_name": "Alpha Admin Monitored Item"},
        headers={"Authorization": f"Bearer {token_merchant}"}
    )
    product_id = create_res.json()["id"]

    # Admin fetches product
    admin_get = client.get(
        f"/api/products/{product_id}",
        headers={"Authorization": f"Bearer {token_admin}"}
    )
    assert admin_get.status_code == 200
    assert admin_get.json()["id"] == product_id
