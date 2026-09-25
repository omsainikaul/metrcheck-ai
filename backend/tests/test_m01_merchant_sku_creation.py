"""
Phase M-01.1 Test Suite: Merchant SKU Creation & Organization Tenant Forensic Verification.

Validates:
1. Merchant with backfilled organization_id can create product SKUs (201 Created).
2. Newly registered Merchant receives automatic authoritative organization tenant.
3. Server authoritatively assigns organization_id and owner_user_id (ignores / overrides client tampering).
4. Product SKU attributes persist accurately (GTIN, MRP, USP, FSSAI, LM registration, etc.).
5. Multi-tenant isolation: Merchant A products are scoped to org A and cannot leak to Merchant B.
6. Anti-IDOR: Merchant B cannot read, modify, or delete Merchant A's products (403/404).
7. RBAC guards: Normal users, Enforcement officers, and Audit officers cannot create products (403 Forbidden).
8. Product Catalog listing and dashboard stats accurately reflect created SKUs for the tenant.
"""

import pytest
import os
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
    hash_password,
)
from database.db import (
    init_db,
    create_user,
    get_user_by_username,
    create_organization,
    get_organization,
    get_product,
    list_products,
    update_user,
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


async def _seed_test_accounts():
    """Setup isolated test accounts for Merchant Phase M-01.1 tests."""
    await init_db()
    pwh, salt = hash_password("SecurePass123!")

    # 1. Merchant A (with explicit org)
    await create_organization("org_merchant_a", "Merchant Alpha Packaging Corp", "MERCHANT")
    await create_user(
        username="m01_merchant_alpha",
        password_hash=pwh,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name="Alpha Merchant",
        email="alpha@merchant.test",
        organization_id="org_merchant_a"
    )

    # 2. Merchant B (with explicit org)
    await create_organization("org_merchant_b", "Merchant Beta Foods Ltd", "MERCHANT")
    await create_user(
        username="m01_merchant_beta",
        password_hash=pwh,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name="Beta Merchant",
        email="beta@merchant.test",
        organization_id="org_merchant_b"
    )

    # 3. Legacy Merchant (created without organization_id to test dynamic backfill)
    await create_user(
        username="m01_legacy_merchant",
        password_hash=pwh,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name="Legacy Merchant User",
        email="legacy@merchant.test",
        organization_id=""
    )

    # 4. Normal Consumer User
    await create_user(
        username="m01_consumer_joe",
        password_hash=pwh,
        salt=salt,
        role=ROLE_USER,
        full_name="Joe Consumer",
        email="joe@consumer.test",
        organization_id="org_user_m01_consumer_joe"
    )

    # 5. Enforcement Officer
    await create_user(
        username="m01_officer_sharma",
        password_hash=pwh,
        salt=salt,
        role=ROLE_ENFORCEMENT,
        full_name="Inspector Sharma",
        email="sharma@gov.test",
        organization_id="org_ministry"
    )

    # 6. Audit Officer
    await create_user(
        username="m01_auditor_verma",
        password_hash=pwh,
        salt=salt,
        role=ROLE_AUDIT,
        full_name="Auditor Verma",
        email="verma@gov.test",
        organization_id="org_ministry"
    )


@pytest.mark.asyncio
async def test_01_merchant_sku_creation_success():
    """Test standard SKU creation by authenticated merchant with valid tenant."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_merchant_alpha", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "product_name": "Crunchy Delight Butter Biscuits 200g",
        "brand_name": "Crunchy Delight",
        "category": "FOOD_BEVERAGE",
        "gtin_barcode": "8901234567890",
        "fssai_license": "10012345678901",
        "legal_metrology_license": "LM/PKG/2026/9876",
        "net_quantity_declared": "200 g",
        "mrp_declared": 45.00,
        "unit_sale_price_declared": "Rs. 0.225 / g",
        "manufacturer_name": "Delight Bakeries Pvt Ltd",
        "country_of_origin": "India"
    }

    resp = client.post("/api/products", json=payload, headers=headers)
    assert resp.status_code == 201, f"Expected 201 Created, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data["product_name"] == "Crunchy Delight Butter Biscuits 200g"
    assert data["organization_id"] == "org_merchant_a"
    assert data["owner_user_id"] == "m01_merchant_alpha"
    assert data["gtin_barcode"] == "8901234567890"
    assert data["fssai_license"] == "10012345678901"
    assert data["legal_metrology_license"] == "LM/PKG/2026/9876"
    assert data["mrp_declared"] == 45.00
    assert data["unit_sale_price_declared"] == "Rs. 0.225 / g"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_02_legacy_merchant_with_missing_org_auto_backfilled():
    """Test that a legacy merchant whose organization_id was empty is dynamically backfilled and succeeds."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_legacy_merchant", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "product_name": "Legacy Brand Tea 500g",
        "brand_name": "Legacy Brand",
        "category": "FOOD_BEVERAGE",
        "mrp_declared": 250.00,
        "net_quantity_declared": "500 g"
    }

    resp = client.post("/api/products", json=payload, headers=headers)
    assert resp.status_code == 201, f"Expected 201 Created for backfilled merchant, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data["product_name"] == "Legacy Brand Tea 500g"
    assert data["organization_id"] == "org_m01_legacy_merchant"
    assert data["owner_user_id"] == "m01_legacy_merchant"

    # Verify user record was updated in database
    user_row = await get_user_by_username("m01_legacy_merchant")
    assert user_row["organization_id"] == "org_m01_legacy_merchant"

    # Verify organization row was created in database
    org_row = await get_organization("org_m01_legacy_merchant")
    assert org_row is not None
    assert org_row["org_type"] == "MERCHANT"


@pytest.mark.asyncio
async def test_03_server_authoritative_tenant_override_tampering():
    """Test that client attempt to pass unauthorized organization_id is rejected or authoritatively overridden."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_merchant_alpha", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to inject org_merchant_b or admin tenant in payload
    payload = {
        "product_name": "Tampered Product",
        "organization_id": "org_merchant_b",
        "owner_user_id": "m01_merchant_beta",
        "mrp_declared": 99.00
    }

    resp = client.post("/api/products", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    # Must be assigned to merchant_alpha's tenant, NOT the injected org_merchant_b
    assert data["organization_id"] == "org_merchant_a"
    assert data["owner_user_id"] == "m01_merchant_alpha"


@pytest.mark.asyncio
async def test_04_cross_tenant_isolation_listing():
    """Test that Merchant A listing products only sees Merchant A products, never Merchant B."""
    await _seed_test_accounts()
    client = TestClient(app)
    token_a = create_token("m01_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("m01_merchant_beta", ROLE_MERCHANT)

    # Product for Alpha
    client.post(
        "/api/products",
        json={"product_name": "Alpha Item 1", "mrp_declared": 10.0},
        headers={"Authorization": f"Bearer {token_a}"}
    )

    # Product for Beta
    client.post(
        "/api/products",
        json={"product_name": "Beta Item 1", "mrp_declared": 20.0},
        headers={"Authorization": f"Bearer {token_b}"}
    )

    # Alpha listing
    resp_a = client.get("/api/products", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    names_a = [p["product_name"] for p in resp_a.json()["products"]]
    assert "Alpha Item 1" in names_a
    assert "Beta Item 1" not in names_a

    # Beta listing
    resp_b = client.get("/api/products", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    names_b = [p["product_name"] for p in resp_b.json()["products"]]
    assert "Beta Item 1" in names_b
    assert "Alpha Item 1" not in names_b


@pytest.mark.asyncio
async def test_05_anti_idor_cross_tenant_product_access():
    """Test that Merchant B cannot fetch, update, or delete Merchant A's product by ID."""
    await _seed_test_accounts()
    client = TestClient(app)
    token_a = create_token("m01_merchant_alpha", ROLE_MERCHANT)
    token_b = create_token("m01_merchant_beta", ROLE_MERCHANT)

    # Create Product A
    create_resp = client.post(
        "/api/products",
        json={"product_name": "Alpha Confidential SKU", "mrp_declared": 100.0},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    product_a_id = create_resp.json()["id"]

    # Merchant B tries to GET Product A
    get_resp = client.get(f"/api/products/{product_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_resp.status_code == 403, f"Expected 403 Forbidden for IDOR GET, got {get_resp.status_code}"

    # Merchant B tries to PATCH Product A
    patch_resp = client.patch(
        f"/api/products/{product_a_id}",
        json={"product_name": "Hacked Product Name"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert patch_resp.status_code == 403, f"Expected 403 Forbidden for IDOR PATCH, got {patch_resp.status_code}"

    # Merchant B tries to DELETE Product A
    del_resp = client.delete(f"/api/products/{product_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_resp.status_code == 403, f"Expected 403 Forbidden for IDOR DELETE, got {del_resp.status_code}"


@pytest.mark.asyncio
async def test_06_rbac_normal_user_cannot_create_products():
    """Test that normal consumer users (ROLE_USER) are blocked from creating products."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_consumer_joe", ROLE_USER)

    resp = client.post(
        "/api/products",
        json={"product_name": "Consumer Rogue SKU", "mrp_declared": 50.0},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403, f"Expected 403 Forbidden for consumer, got {resp.status_code}"


@pytest.mark.asyncio
async def test_07_rbac_enforcement_officer_cannot_create_products():
    """Test that enforcement officers (ROLE_ENFORCEMENT) cannot create merchant products."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_officer_sharma", ROLE_ENFORCEMENT)

    resp = client.post(
        "/api/products",
        json={"product_name": "Officer Rogue SKU", "mrp_declared": 50.0},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403, f"Expected 403 Forbidden for officer, got {resp.status_code}"


@pytest.mark.asyncio
async def test_08_rbac_audit_officer_cannot_create_products():
    """Test that audit officers (ROLE_AUDIT) cannot create merchant products."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_auditor_verma", ROLE_AUDIT)

    resp = client.post(
        "/api/products",
        json={"product_name": "Auditor Rogue SKU", "mrp_declared": 50.0},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403, f"Expected 403 Forbidden for auditor, got {resp.status_code}"


@pytest.mark.asyncio
async def test_09_product_update_and_soft_archive_lifecycle():
    """Test product metadata update and non-destructive soft-archiving by owner merchant."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_merchant_alpha", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create product
    create_resp = client.post(
        "/api/products",
        json={
            "product_name": "Initial Name",
            "mrp_declared": 50.0,
            "net_quantity_declared": "100 g"
        },
        headers=headers
    )
    pid = create_resp.json()["id"]

    # 2. Update product
    update_resp = client.patch(
        f"/api/products/{pid}",
        json={
            "product_name": "Updated Premium Name",
            "mrp_declared": 65.0,
            "unit_sale_price_declared": "Rs. 0.65 / g"
        },
        headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["product_name"] == "Updated Premium Name"
    assert update_resp.json()["mrp_declared"] == 65.0
    assert update_resp.json()["unit_sale_price_declared"] == "Rs. 0.65 / g"

    # 3. Soft archive product
    del_resp = client.delete(f"/api/products/{pid}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ARCHIVED"

    # 4. Verify product status in DB
    prod = await get_product(pid)
    assert prod["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_10_merchant_dashboard_stats_aggregation():
    """Test that merchant dashboard metrics accurately reflect created product SKUs."""
    await _seed_test_accounts()
    client = TestClient(app)
    token = create_token("m01_merchant_alpha", ROLE_MERCHANT)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch initial stats
    stats_resp = client.get("/api/products/stats", headers=headers)
    assert stats_resp.status_code == 200
    initial_active = stats_resp.json()["active_products"]

    # Create 2 new products
    client.post("/api/products", json={"product_name": "SKU 1", "mrp_declared": 10.0}, headers=headers)
    client.post("/api/products", json={"product_name": "SKU 2", "mrp_declared": 20.0}, headers=headers)

    # Fetch updated stats
    updated_stats = client.get("/api/products/stats", headers=headers).json()
    assert updated_stats["active_products"] == initial_active + 2
