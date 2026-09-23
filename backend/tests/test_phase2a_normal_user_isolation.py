import pytest
import os
import json
import time
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
    create_user,
    save_analysis,
    get_analysis,
    get_analyses,
    get_stats,
    create_organization,
    get_user_by_username
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


@pytest.mark.asyncio
async def test_normal_user_statistics_isolation():
    """
    Test 1: Normal User statistics endpoints (/api/stats, /api/stats/trends, /api/stats/by-status)
    must strictly filter to only analyses owned by that specific normal user.
    """
    client = TestClient(app)
    pwh, salt = hash_password("userpass123")

    # Create Normal Users
    await create_user("p2a_user1", pwh, salt, ROLE_USER, full_name="User One")
    await create_user("p2a_user2", pwh, salt, ROLE_USER, full_name="User Two")
    await create_user("p2a_merchant", pwh, salt, ROLE_MERCHANT, full_name="Merchant P2A", organization_id="org_p2a_merchant")

    token_user1 = create_token("p2a_user1", ROLE_USER)
    token_user2 = create_token("p2a_user2", ROLE_USER)

    # Seed 3 scans for User 1 (2 Compliant, 1 Failure)
    for i in range(2):
        await save_analysis({
            "id": f"scan-u1-comp-{i}",
            "product_name": f"User 1 Compliant Product {i}",
            "image_filename": f"scan-u1-comp-{i}.png",
            "ocr_text": "Net Qty 500g MRP Rs 50",
            "extracted_data": {"net_quantity": "500g", "mrp": "Rs 50"},
            "compliance_result": {"checks": [{"status": "PASS"}], "status": "COMPLIANT", "compliance_score": 100},
            "score": 100.0,
            "status": "COMPLIANT",
            "created_at": "2026-09-15T10:00:00Z",
            "owner_user_id": "p2a_user1",
            "organization_id": "org_user_p2a_user1"
        })
    await save_analysis({
        "id": "scan-u1-fail-0",
        "product_name": "User 1 Failed Product",
        "image_filename": "scan-u1-fail-0.png",
        "ocr_text": "No Net Qty No MRP",
        "extracted_data": {},
        "compliance_result": {"checks": [{"status": "FAIL"}], "status": "NON_COMPLIANT", "compliance_score": 30},
        "score": 30.0,
        "status": "NON_COMPLIANT",
        "created_at": "2026-09-15T11:00:00Z",
        "owner_user_id": "p2a_user1",
        "organization_id": "org_user_p2a_user1"
    })

    # Seed 2 scans for User 2 (2 Compliant)
    for i in range(2):
        await save_analysis({
            "id": f"scan-u2-comp-{i}",
            "product_name": f"User 2 Compliant Product {i}",
            "image_filename": f"scan-u2-comp-{i}.png",
            "ocr_text": "Net Qty 1L MRP Rs 90",
            "extracted_data": {"net_quantity": "1L", "mrp": "Rs 90"},
            "compliance_result": {"checks": [{"status": "PASS"}], "status": "COMPLIANT", "compliance_score": 100},
            "score": 100.0,
            "status": "COMPLIANT",
            "created_at": "2026-09-15T12:00:00Z",
            "owner_user_id": "p2a_user2",
            "organization_id": "org_user_p2a_user2"
        })

    # Seed 5 scans for Merchant
    for i in range(5):
        await save_analysis({
            "id": f"scan-merch-{i}",
            "product_name": f"Merchant Product {i}",
            "image_filename": f"scan-merch-{i}.png",
            "ocr_text": "Net Qty 2kg MRP Rs 200",
            "extracted_data": {"net_quantity": "2kg", "mrp": "Rs 200"},
            "compliance_result": {"checks": [{"status": "PASS"}], "status": "COMPLIANT", "compliance_score": 100},
            "score": 100.0,
            "status": "COMPLIANT",
            "created_at": "2026-09-15T13:00:00Z",
            "owner_user_id": "p2a_merchant",
            "organization_id": "org_p2a_merchant"
        })

    # Query stats as User 1
    resp_u1_stats = client.get("/api/stats", headers={"Authorization": f"Bearer {token_user1}"})
    assert resp_u1_stats.status_code == 200
    u1_data = resp_u1_stats.json()
    assert u1_data["total_analyzed"] == 3
    assert u1_data["compliant"] == 2
    assert u1_data["failures"] == 1
    for recent_item in u1_data["recent"]:
        assert recent_item["owner_user_id"] == "p2a_user1"

    # Query /api/stats/by-status as User 1
    resp_u1_by_status = client.get("/api/stats/by-status", headers={"Authorization": f"Bearer {token_user1}"})
    assert resp_u1_by_status.status_code == 200
    by_status_data = resp_u1_by_status.json()
    assert sum(by_status_data["values"]) == 3

    # Query stats as User 2
    resp_u2_stats = client.get("/api/stats", headers={"Authorization": f"Bearer {token_user2}"})
    assert resp_u2_stats.status_code == 200
    u2_data = resp_u2_stats.json()
    assert u2_data["total_analyzed"] == 2
    assert u2_data["compliant"] == 2
    assert u2_data["failures"] == 0
    for recent_item in u2_data["recent"]:
        assert recent_item["owner_user_id"] == "p2a_user2"


@pytest.mark.asyncio
async def test_normal_user_delete_own_scan_success():
    """
    Test 2: Normal User can successfully delete their own personal scan record.
    The database record and associated image files must be cleanly deleted.
    """
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2a_delete_user", pwh, salt, ROLE_USER, full_name="Delete User")
    token_user = create_token("p2a_delete_user", ROLE_USER)

    scan_id = "p2a-user-own-scan-1"
    test_img = os.path.join(settings.UPLOAD_DIR, f"{scan_id}_front.png")
    with open(test_img, "wb") as f:
        f.write(b'USER_SCAN_IMAGE_DATA')

    await save_analysis({
        "id": scan_id,
        "product_name": "Personal User Test Item",
        "image_filename": f"{scan_id}_front.png",
        "ocr_text": "Net Qty 100g MRP Rs 20",
        "extracted_data": {"net_quantity": "100g", "mrp": "Rs 20"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-16T10:00:00Z",
        "images": [{"filename": f"{scan_id}_front.png", "image_url": f"/api/images/{scan_id}_front.png"}],
        "owner_user_id": "p2a_delete_user",
        "organization_id": "org_user_p2a_delete_user"
    })

    # Ensure it exists first
    assert os.path.exists(test_img)
    assert await get_analysis(scan_id) is not None

    # Delete scan as the owner
    del_resp = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_user}"})
    assert del_resp.status_code == 200
    assert del_resp.json()["id"] == scan_id

    # Verify deleted from DB and files removed
    assert not os.path.exists(test_img), "Image file must be cleaned up on deletion"
    assert await get_analysis(scan_id) is None, "Analysis must be deleted from database"

    # Subsequent GET returns 404
    get_resp = client.get(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_user}"})
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_normal_user_cannot_delete_other_user_scan():
    """
    Test 3: Normal User A cannot delete Normal User B's scan (403 Forbidden).
    User B's scan record and uploaded files must remain intact.
    """
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2a_attacker_user", pwh, salt, ROLE_USER, full_name="Attacker User")
    await create_user("p2a_victim_user", pwh, salt, ROLE_USER, full_name="Victim User")

    token_attacker = create_token("p2a_attacker_user", ROLE_USER)

    victim_scan_id = "p2a-victim-scan-1"
    victim_img = os.path.join(settings.UPLOAD_DIR, f"{victim_scan_id}_front.png")
    with open(victim_img, "wb") as f:
        f.write(b'VICTIM_IMAGE_BYTES')

    await save_analysis({
        "id": victim_scan_id,
        "product_name": "Victim's Personal Item",
        "image_filename": f"{victim_scan_id}_front.png",
        "ocr_text": "Net Qty 250ml MRP Rs 40",
        "extracted_data": {"net_quantity": "250ml", "mrp": "Rs 40"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-16T11:00:00Z",
        "images": [{"filename": f"{victim_scan_id}_front.png", "image_url": f"/api/images/{victim_scan_id}_front.png"}],
        "owner_user_id": "p2a_victim_user",
        "organization_id": "org_user_p2a_victim_user"
    })

    # Attacker tries to delete Victim's scan
    del_resp = client.delete(f"/api/history/{victim_scan_id}", headers={"Authorization": f"Bearer {token_attacker}"})
    assert del_resp.status_code == 403
    assert "You do not have permission" in del_resp.json()["detail"]

    # Target data must be completely preserved
    assert os.path.exists(victim_img), "Victim's image must not be deleted"
    assert await get_analysis(victim_scan_id) is not None, "Victim's DB record must not be deleted"


@pytest.mark.asyncio
async def test_normal_user_cannot_delete_merchant_or_officer_scan():
    """
    Test 4: Normal User cannot delete scans belonging to Merchants or Officers (403 Forbidden).
    """
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2a_normie", pwh, salt, ROLE_USER, full_name="Normie")
    await create_user("p2a_corp_merchant", pwh, salt, ROLE_MERCHANT, full_name="Corp Merchant", organization_id="org_corp_p2a")

    token_user = create_token("p2a_normie", ROLE_USER)

    merchant_scan_id = "p2a-corp-scan-1"
    merch_img = os.path.join(settings.UPLOAD_DIR, f"{merchant_scan_id}_front.png")
    with open(merch_img, "wb") as f:
        f.write(b'CORP_MERCHANT_IMAGE')

    await save_analysis({
        "id": merchant_scan_id,
        "product_name": "Corporate Packaged Goods",
        "image_filename": f"{merchant_scan_id}_front.png",
        "ocr_text": "Net Qty 5kg MRP Rs 500",
        "extracted_data": {"net_quantity": "5kg", "mrp": "Rs 500"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-16T12:00:00Z",
        "images": [{"filename": f"{merchant_scan_id}_front.png", "image_url": f"/api/images/{merchant_scan_id}_front.png"}],
        "owner_user_id": "p2a_corp_merchant",
        "organization_id": "org_corp_p2a"
    })

    # Normal user attempts to delete corporate scan
    del_resp = client.delete(f"/api/history/{merchant_scan_id}", headers={"Authorization": f"Bearer {token_user}"})
    assert del_resp.status_code == 403
    assert os.path.exists(merch_img)
    assert await get_analysis(merchant_scan_id) is not None


@pytest.mark.asyncio
async def test_merchant_cannot_delete_normal_user_scan():
    """
    Test 5: Merchant cannot delete a Normal User's scan (403 Forbidden).
    """
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2a_merchant_intruder", pwh, salt, ROLE_MERCHANT, full_name="Intruder Merchant", organization_id="org_intruder")
    await create_user("p2a_innocent_user", pwh, salt, ROLE_USER, full_name="Innocent User")

    token_merchant = create_token("p2a_merchant_intruder", ROLE_MERCHANT)

    user_scan_id = "p2a-innocent-user-scan"
    user_img = os.path.join(settings.UPLOAD_DIR, f"{user_scan_id}_front.png")
    with open(user_img, "wb") as f:
        f.write(b'USER_ASSET_BYTES')

    await save_analysis({
        "id": user_scan_id,
        "product_name": "Innocent User Scan",
        "image_filename": f"{user_scan_id}_front.png",
        "ocr_text": "Net Qty 100ml",
        "extracted_data": {"net_quantity": "100ml"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-16T13:00:00Z",
        "images": [{"filename": f"{user_scan_id}_front.png", "image_url": f"/api/images/{user_scan_id}_front.png"}],
        "owner_user_id": "p2a_innocent_user",
        "organization_id": "org_user_p2a_innocent_user"
    })

    # Merchant attempts to delete Normal User scan -> 403 Forbidden
    resp = client.delete(f"/api/history/{user_scan_id}", headers={"Authorization": f"Bearer {token_merchant}"})
    assert resp.status_code == 403
    assert os.path.exists(user_img)
    assert await get_analysis(user_scan_id) is not None


@pytest.mark.asyncio
async def test_officer_deletion_permissions():
    """
    Test 6: Audit Officer cannot delete scans (403), Enforcement Officer can delete within jurisdiction.
    """
    client = TestClient(app)
    pwh, salt = hash_password("pass123")

    await create_organization({"id": "org_p2a_state", "name": "State Metrology", "status": "ACTIVE"})
    await create_user("p2a_audit_off", pwh, salt, ROLE_AUDIT, full_name="Audit Off", organization_id="org_p2a_state")
    await create_user("p2a_enf_off", pwh, salt, ROLE_ENFORCEMENT, full_name="Enf Off", organization_id="org_p2a_state")

    token_audit = create_token("p2a_audit_off", ROLE_AUDIT)
    token_enf = create_token("p2a_enf_off", ROLE_ENFORCEMENT)

    scan_id = "p2a-state-case-001"
    test_img = os.path.join(settings.UPLOAD_DIR, f"{scan_id}_front.png")
    with open(test_img, "wb") as f:
        f.write(b'OFFICIAL_CASE_EVIDENCE')

    await save_analysis({
        "id": scan_id,
        "product_name": "Enforcement Sample",
        "image_filename": f"{scan_id}_front.png",
        "ocr_text": "Sample Net Qty 50g",
        "extracted_data": {"net_quantity": "50g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-16T14:00:00Z",
        "images": [{"filename": f"{scan_id}_front.png", "image_url": f"/api/images/{scan_id}_front.png"}],
        "owner_user_id": "p2a_audit_off",
        "organization_id": "org_p2a_state"
    })

    # Audit Officer attempts deletion -> 403
    resp_audit = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_audit}"})
    assert resp_audit.status_code == 403
    assert "Insufficient privileges" in resp_audit.json()["detail"]
    assert await get_analysis(scan_id) is not None

    # Enforcement Officer in same org deletes -> 200 OK
    resp_enf = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_enf}"})
    assert resp_enf.status_code == 200
    assert not os.path.exists(test_img)
    assert await get_analysis(scan_id) is None


@pytest.mark.asyncio
async def test_admin_deletion_power():
    """
    Test 7: Admin can delete any user/merchant scan.
    """
    client = TestClient(app)
    pwh, salt = hash_password("adminpass")
    await create_user("p2a_admin_user", pwh, salt, ROLE_ADMIN, full_name="Admin Boss", organization_id="org_ministry")
    token_admin = create_token("p2a_admin_user", ROLE_ADMIN)

    scan_id = "p2a-user-for-admin-del"
    test_img = os.path.join(settings.UPLOAD_DIR, f"{scan_id}_front.png")
    with open(test_img, "wb") as f:
        f.write(b'IMAGE_TO_BE_PURGED_BY_ADMIN')

    await save_analysis({
        "id": scan_id,
        "product_name": "Admin Cleanup Target",
        "image_filename": f"{scan_id}_front.png",
        "ocr_text": "Net Qty 10g",
        "extracted_data": {"net_quantity": "10g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-16T15:00:00Z",
        "images": [{"filename": f"{scan_id}_front.png", "image_url": f"/api/images/{scan_id}_front.png"}],
        "owner_user_id": "some_random_user",
        "organization_id": "org_random_tenant"
    })

    resp = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200
    assert not os.path.exists(test_img)
    assert await get_analysis(scan_id) is None


@pytest.mark.asyncio
async def test_protected_demo_deletion_blocked():
    """
    Test 8: Demo benchmarks (demo-*, 1, 2, 3) cannot be deleted by anyone, including normal users and admins.
    """
    client = TestClient(app)
    pwh, salt = hash_password("pass")
    await create_user("p2a_demo_try_user", pwh, salt, ROLE_USER)
    await create_user("p2a_demo_try_admin", pwh, salt, ROLE_ADMIN)

    token_user = create_token("p2a_demo_try_user", ROLE_USER)
    token_admin = create_token("p2a_demo_try_admin", ROLE_ADMIN)

    for demo_id in ["demo-1", "demo-packaged-rice", "1", "2", "3"]:
        resp_u = client.delete(f"/api/history/{demo_id}", headers={"Authorization": f"Bearer {token_user}"})
        assert resp_u.status_code == 403
        assert "Demonstration benchmark cases are protected" in resp_u.json()["detail"]

        resp_a = client.delete(f"/api/history/{demo_id}", headers={"Authorization": f"Bearer {token_admin}"})
        assert resp_a.status_code == 403
        assert "Demonstration benchmark cases are protected" in resp_a.json()["detail"]
