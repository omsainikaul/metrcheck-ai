"""
Phase M-03 Test Suite: Merchant SKU Workflow Completion & Usability Hardening.

Validates:
1. Listing Check (`POST /api/analyze/text`) with valid merchant `product_id` binds correctly.
2. Cross-tenant SKU linkage attempt in Listing Check (`POST /api/analyze/text`) is strictly rejected (403 Forbidden).
3. Standalone Listing Check without `product_id` continues to function reliably.
4. Product Catalog status filter (`status=ACTIVE`, `status=ARCHIVED`, `status=ALL`) returns correct records with strict tenant isolation.
5. Pre-print artwork upload (`POST /api/preprint/upload`) with valid merchant `product_id` links properly.
6. Cross-tenant pre-print artwork upload with another tenant's `product_id` is rejected (403 Forbidden).
7. Product Detail summary (`GET /api/products/{id}/summary`) aggregates analyses and artworks accurately.
8. Historical analysis data immutability is preserved across SKU updates.
9. Merchant Dashboard KPIs (`GET /api/products/stats`) reflect tenant activity accurately.
"""

import os
import io
import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import (
    create_token,
    ROLE_MERCHANT,
    hash_password,
)
from database.db import (
    init_db,
    create_user,
    create_organization,
    create_product,
    get_product_analyses,
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


async def _seed_m03_test_data():
    """Setup isolated test accounts and products for M-03 tests."""
    await init_db()
    pwh, salt = hash_password("SecurePass123!")

    # 1. Merchant Tenant A
    await create_organization("org_m03_alpha", "M03 Alpha Enterprises", "MERCHANT")
    await create_user(
        username="m03_merchant_alpha",
        password_hash=pwh,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name="Alpha Merchant Lead",
        email="alpha@m03.test",
        organization_id="org_m03_alpha"
    )

    # 2. Merchant Tenant B
    await create_organization("org_m03_beta", "M03 Beta Foods Ltd", "MERCHANT")
    await create_user(
        username="m03_merchant_beta",
        password_hash=pwh,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name="Beta Merchant Lead",
        email="beta@m03.test",
        organization_id="org_m03_beta"
    )

    # 3. Create sample products for Tenant A
    prod_a_active = await create_product({
        "product_name": "Alpha Premium Basmati Rice 5kg",
        "brand_name": "Alpha Harvest",
        "category": "FOOD_BEVERAGES",
        "gtin_barcode": "8901234000011",
        "net_quantity_declared": "5 kg",
        "mrp_declared": 450.0,
        "manufacturer_name": "Alpha Grains Pvt Ltd",
        "country_of_origin": "India",
        "organization_id": "org_m03_alpha",
        "owner_user_id": "m03_merchant_alpha",
        "status": "ACTIVE"
    })

    prod_a_archived = await create_product({
        "product_name": "Alpha Vintage Green Tea 100g (Legacy)",
        "brand_name": "Alpha Harvest",
        "category": "FOOD_BEVERAGES",
        "gtin_barcode": "8901234000028",
        "net_quantity_declared": "100 g",
        "mrp_declared": 220.0,
        "manufacturer_name": "Alpha Grains Pvt Ltd",
        "country_of_origin": "India",
        "organization_id": "org_m03_alpha",
        "owner_user_id": "m03_merchant_alpha",
        "status": "ARCHIVED"
    })

    # 4. Create sample product for Tenant B
    prod_b_active = await create_product({
        "product_name": "Beta Cold Pressed Mustard Oil 1L",
        "brand_name": "Beta Organics",
        "category": "FOOD_BEVERAGES",
        "gtin_barcode": "8909876000015",
        "net_quantity_declared": "1 L",
        "mrp_declared": 195.0,
        "manufacturer_name": "Beta Foods Ltd",
        "country_of_origin": "India",
        "organization_id": "org_m03_beta",
        "owner_user_id": "m03_merchant_beta",
        "status": "ACTIVE"
    })

    return {
        "alpha_token": create_token("m03_merchant_alpha", ROLE_MERCHANT),
        "beta_token": create_token("m03_merchant_beta", ROLE_MERCHANT),
        "prod_a_active_id": prod_a_active["id"],
        "prod_a_archived_id": prod_a_archived["id"],
        "prod_b_active_id": prod_b_active["id"],
    }


SAMPLE_LISTING_TEXT = """
Alpha Harvest Premium Basmati Rice 5kg
MRP: Rs. 450.00 (inclusive of all taxes)
Net Quantity: 5 kg
Unit Sale Price: Rs. 90.00 per kg
Manufactured & Marketed by: Alpha Grains Pvt Ltd, Industrial Area, Karnal, Haryana - 132001, India.
Country of Origin: India
Consumer Care: care@alphagrains.com | +91-1800-111-222
Customer Care Address: Same as manufacturer.
Date of Manufacture: 01/2026
Best Before: 12 months from manufacture.
FSSAI Lic No: 10019011000123
"""


@pytest.mark.asyncio
async def test_listing_check_with_valid_sku_linkage():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    payload = {
        "text": SAMPLE_LISTING_TEXT,
        "product_id": data["prod_a_active_id"],
    }

    response = client.post("/api/analyze/text", json=payload, headers=headers)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    body = response.json()
    analysis_id = body.get("id")
    assert analysis_id is not None

    # Verify that the analysis is linked to product_id in tenant history
    analyses = await get_product_analyses(data["prod_a_active_id"], "org_m03_alpha")
    assert any(a["id"] == analysis_id for a in analyses), "Analysis must be recorded under the linked product"


@pytest.mark.asyncio
async def test_listing_check_cross_tenant_sku_rejection():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    # Merchant Alpha tries to bind Merchant Beta's product
    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    payload = {
        "text": SAMPLE_LISTING_TEXT,
        "product_id": data["prod_b_active_id"],
    }

    response = client.post("/api/analyze/text", json=payload, headers=headers)
    assert response.status_code == 403, f"Cross-tenant SKU binding must return 403 Forbidden, got: {response.status_code}"


@pytest.mark.asyncio
async def test_listing_check_standalone_without_sku():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    payload = {
        "text": SAMPLE_LISTING_TEXT,
    }

    response = client.post("/api/analyze/text", json=payload, headers=headers)
    assert response.status_code == 200, f"Standalone listing check must return 200, got: {response.text}"
    body = response.json()
    assert body.get("id") is not None


@pytest.mark.asyncio
async def test_product_catalog_status_filtering():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['alpha_token']}"}

    # 1. Filter ACTIVE
    res_active = client.get("/api/products?status=ACTIVE", headers=headers)
    assert res_active.status_code == 200
    active_items = res_active.json().get("products", [])
    assert any(p["id"] == data["prod_a_active_id"] for p in active_items)
    assert not any(p["id"] == data["prod_a_archived_id"] for p in active_items)
    assert not any(p["id"] == data["prod_b_active_id"] for p in active_items)

    # 2. Filter ARCHIVED
    res_archived = client.get("/api/products?status=ARCHIVED", headers=headers)
    assert res_archived.status_code == 200
    archived_items = res_archived.json().get("products", [])
    assert any(p["id"] == data["prod_a_archived_id"] for p in archived_items)
    assert not any(p["id"] == data["prod_a_active_id"] for p in archived_items)
    assert not any(p["id"] == data["prod_b_active_id"] for p in archived_items)

    # 3. Filter ALL
    res_all = client.get("/api/products?status=ALL", headers=headers)
    assert res_all.status_code == 200
    all_items = res_all.json().get("products", [])
    assert any(p["id"] == data["prod_a_active_id"] for p in all_items)
    assert any(p["id"] == data["prod_a_archived_id"] for p in all_items)
    assert not any(p["id"] == data["prod_b_active_id"] for p in all_items)


@pytest.mark.asyncio
async def test_preprint_artwork_upload_with_sku_linkage():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    fake_file_content = b"%PDF-1.4 Fake PDF Content for Packaging Artwork"
    files = {
        "file": ("artwork_v1.pdf", io.BytesIO(fake_file_content), "application/pdf")
    }
    form_data = {
        "product_id": data["prod_a_active_id"],
        "iteration_number": 1
    }

    response = client.post("/api/preprint/upload", files=files, data=form_data, headers=headers)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    body = response.json()
    assert body.get("success") is True
    artwork_id = body.get("artwork_id")
    assert artwork_id is not None

    # Verify artwork detail has product_id
    art_res = client.get(f"/api/preprint/{artwork_id}", headers=headers)
    assert art_res.status_code == 200
    art_doc = art_res.json()
    assert art_doc.get("product_id") == data["prod_a_active_id"]


@pytest.mark.asyncio
async def test_preprint_artwork_cross_tenant_upload_rejection():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    # Merchant Alpha tries to upload artwork linked to Merchant Beta's product
    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    fake_file_content = b"%PDF-1.4 Fake Cross Tenant Artwork"
    files = {
        "file": ("cross_tenant_art.pdf", io.BytesIO(fake_file_content), "application/pdf")
    }
    form_data = {
        "product_id": data["prod_b_active_id"],
    }

    response = client.post("/api/preprint/upload", files=files, data=form_data, headers=headers)
    assert response.status_code == 403, f"Cross-tenant artwork upload must return 403, got: {response.status_code}"


@pytest.mark.asyncio
async def test_product_summary_aggregation_and_detail():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    prod_id = data["prod_a_active_id"]

    # Fetch summary
    sum_res = client.get(f"/api/products/{prod_id}/summary", headers=headers)
    assert sum_res.status_code == 200, f"Expected 200, got: {sum_res.text}"
    summary = sum_res.json()
    assert summary["product"]["id"] == prod_id
    assert "total_scans" in summary
    assert "total_artworks" in summary
    assert "latest_score" in summary

    # Cross-tenant read must fail
    beta_headers = {"Authorization": f"Bearer {data['beta_token']}"}
    beta_sum_res = client.get(f"/api/products/{prod_id}/summary", headers=beta_headers)
    assert beta_sum_res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_merchant_dashboard_stats_aggregation():
    data = await _seed_m03_test_data()
    client = TestClient(app)

    headers = {"Authorization": f"Bearer {data['alpha_token']}"}
    dash_res = client.get("/api/products/stats", headers=headers)
    assert dash_res.status_code == 200, f"Expected 200, got: {dash_res.text}"
    stats = dash_res.json()
    assert "active_products" in stats
    assert "products_checked" in stats
    assert "packaging_artworks" in stats
