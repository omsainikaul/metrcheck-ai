import pytest
import os
import json
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
    create_organization,
    get_user_by_username
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Test attempted to run against production database!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Test attempted to run against production uploads directory!"


@pytest.mark.asyncio
async def test_01_public_user_dashboard_stats_contain_only_own_data():
    """TEST 1: PUBLIC_USER dashboard statistics contain only own data."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_user1", pwh, salt, ROLE_USER, full_name="User 1")
    await create_user("p2b_user2", pwh, salt, ROLE_USER, full_name="User 2")
    token_u1 = create_token("p2b_user1", ROLE_USER)

    await save_analysis({
        "id": "p2b-u1-scan-1",
        "product_name": "User 1 Biscuit",
        "image_filename": "u1_1.png",
        "ocr_text": "Net Qty 100g MRP Rs 30",
        "extracted_data": {"net_quantity": "100g", "mrp": "Rs 30"},
        "compliance_result": {
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "net_quantity",
                    "field_label": "Net Quantity",
                    "status": "PASS",
                    "detected_value": "100g",
                    "required_format": "Metric unit",
                    "confidence": 0.98,
                    "severity": "CRITICAL",
                    "explanation": "Net quantity is compliant"
                }
            ],
            "status": "COMPLIANT",
            "compliance_score": 100
        },
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T10:00:00Z",
        "owner_user_id": "p2b_user1",
        "organization_id": "org_user_p2b_user1"
    })
    await save_analysis({
        "id": "p2b-u2-scan-1",
        "product_name": "User 2 Chips",
        "image_filename": "u2_1.png",
        "ocr_text": "Net Qty 50g MRP Rs 20",
        "extracted_data": {"net_quantity": "50g", "mrp": "Rs 20"},
        "compliance_result": {
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "net_quantity",
                    "field_label": "Net Quantity",
                    "status": "PASS",
                    "detected_value": "50g",
                    "required_format": "Metric unit",
                    "confidence": 0.98,
                    "severity": "CRITICAL",
                    "explanation": "Net quantity is compliant"
                }
            ],
            "status": "COMPLIANT",
            "compliance_score": 100
        },
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T10:05:00Z",
        "owner_user_id": "p2b_user2",
        "organization_id": "org_user_p2b_user2"
    })

    resp = client.get("/api/stats", headers={"Authorization": f"Bearer {token_u1}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_analyzed"] == 1
    assert data["compliant"] == 1
    assert data["recent"][0]["product_name"] == "User 1 Biscuit"


@pytest.mark.asyncio
async def test_02_public_user_history_contains_only_own_scans():
    """TEST 2: PUBLIC_USER history contains only own scans."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_hist_u1", pwh, salt, ROLE_USER, full_name="Hist User 1")
    await create_user("p2b_hist_u2", pwh, salt, ROLE_USER, full_name="Hist User 2")
    token_u1 = create_token("p2b_hist_u1", ROLE_USER)

    await save_analysis({
        "id": "p2b-hist-u1-item",
        "product_name": "User 1 Tea",
        "image_filename": "u1_tea.png",
        "ocr_text": "Net Qty 250g MRP Rs 120",
        "extracted_data": {"net_quantity": "250g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T11:00:00Z",
        "owner_user_id": "p2b_hist_u1",
        "organization_id": "org_user_p2b_hist_u1"
    })
    await save_analysis({
        "id": "p2b-hist-u2-item",
        "product_name": "User 2 Coffee",
        "image_filename": "u2_coffee.png",
        "ocr_text": "Net Qty 200g MRP Rs 250",
        "extracted_data": {"net_quantity": "200g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T11:05:00Z",
        "owner_user_id": "p2b_hist_u2",
        "organization_id": "org_user_p2b_hist_u2"
    })

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token_u1}"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == "p2b-hist-u1-item"
    assert items[0]["product_name"] == "User 1 Tea"


@pytest.mark.asyncio
async def test_03_public_user_can_open_own_scan():
    """TEST 3: PUBLIC_USER can open own scan."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_open_u1", pwh, salt, ROLE_USER, full_name="Open User")
    token_u = create_token("p2b_open_u1", ROLE_USER)

    scan_id = "p2b-open-own-scan"
    await save_analysis({
        "id": scan_id,
        "product_name": "Own Soap",
        "image_filename": "soap.png",
        "ocr_text": "Net Qty 125g MRP Rs 45",
        "extracted_data": {"net_quantity": "125g", "mrp": "Rs 45"},
        "compliance_result": {
            "checks": [
                {
                    "rule_id": "LM-001",
                    "field": "net_quantity",
                    "field_label": "Net Qty",
                    "status": "PASS",
                    "detected_value": "125g",
                    "required_format": "Metric unit",
                    "confidence": 0.99,
                    "severity": "CRITICAL",
                    "explanation": "Net quantity is compliant"
                }
            ],
            "status": "COMPLIANT",
            "compliance_score": 100
        },
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T12:00:00Z",
        "owner_user_id": "p2b_open_u1",
        "organization_id": "org_user_p2b_open_u1"
    })

    resp = client.get(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_u}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == scan_id
    assert data["product_name"] == "Own Soap"


@pytest.mark.asyncio
async def test_04_public_user_cannot_open_other_user_scan():
    """TEST 4: PUBLIC_USER cannot open another user's scan (403 Forbidden)."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_intruder_user", pwh, salt, ROLE_USER)
    await create_user("p2b_target_user", pwh, salt, ROLE_USER)

    token_intruder = create_token("p2b_intruder_user", ROLE_USER)

    target_id = "p2b-target-secret-scan"
    await save_analysis({
        "id": target_id,
        "product_name": "Target Private Item",
        "image_filename": "target.png",
        "ocr_text": "Net Qty 1L MRP Rs 150",
        "extracted_data": {"net_quantity": "1L", "mrp": "Rs 150"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T12:30:00Z",
        "owner_user_id": "p2b_target_user",
        "organization_id": "org_user_p2b_target_user"
    })

    resp = client.get(f"/api/history/{target_id}", headers={"Authorization": f"Bearer {token_intruder}"})
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_05_public_user_can_delete_own_scan():
    """TEST 5: PUBLIC_USER can delete own scan."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_del_u", pwh, salt, ROLE_USER)
    token_u = create_token("p2b_del_u", ROLE_USER)

    scan_id = "p2b-del-own-item"
    await save_analysis({
        "id": scan_id,
        "product_name": "Item To Delete",
        "image_filename": "item_del.png",
        "ocr_text": "Net Qty 500g",
        "extracted_data": {"net_quantity": "500g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T13:00:00Z",
        "owner_user_id": "p2b_del_u",
        "organization_id": "org_user_p2b_del_u"
    })

    resp = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_u}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == scan_id
    assert await get_analysis(scan_id) is None


@pytest.mark.asyncio
async def test_06_public_user_cannot_delete_other_user_scan():
    """TEST 6: PUBLIC_USER cannot delete another user's scan."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_del_hacker", pwh, salt, ROLE_USER)
    await create_user("p2b_del_innocent", pwh, salt, ROLE_USER)
    token_hacker = create_token("p2b_del_hacker", ROLE_USER)

    scan_id = "p2b-innocent-permanent-scan"
    await save_analysis({
        "id": scan_id,
        "product_name": "Innocent Scan",
        "image_filename": "innocent.png",
        "ocr_text": "Net Qty 100g",
        "extracted_data": {"net_quantity": "100g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T13:30:00Z",
        "owner_user_id": "p2b_del_innocent",
        "organization_id": "org_user_p2b_del_innocent"
    })

    resp = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_hacker}"})
    assert resp.status_code == 403
    assert await get_analysis(scan_id) is not None


@pytest.mark.asyncio
async def test_07_public_user_can_download_own_report():
    """TEST 7: PUBLIC_USER can download own report."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_rep_u", pwh, salt, ROLE_USER)
    token_u = create_token("p2b_rep_u", ROLE_USER)

    scan_id = "p2b-rep-own-scan"
    await save_analysis({
        "id": scan_id,
        "product_name": "Report Target Product",
        "image_filename": "report_target.png",
        "ocr_text": "Net Qty 1kg MRP Rs 199",
        "extracted_data": {"net_quantity": "1kg", "mrp": "Rs 199"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T14:00:00Z",
        "owner_user_id": "p2b_rep_u",
        "organization_id": "org_user_p2b_rep_u"
    })

    # Download CSV Report
    resp_csv = client.get(f"/api/report/{scan_id}/csv", headers={"Authorization": f"Bearer {token_u}"})
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers.get("content-type", "")

    # Download JSON Report
    resp_json = client.get(f"/api/report/{scan_id}/json", headers={"Authorization": f"Bearer {token_u}"})
    assert resp_json.status_code == 200


@pytest.mark.asyncio
async def test_08_public_user_cannot_download_other_user_report():
    """TEST 8: PUBLIC_USER cannot download another user's report."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_rep_intruder", pwh, salt, ROLE_USER)
    await create_user("p2b_rep_victim", pwh, salt, ROLE_USER)
    token_intruder = create_token("p2b_rep_intruder", ROLE_USER)

    scan_id = "p2b-victim-secret-report"
    await save_analysis({
        "id": scan_id,
        "product_name": "Victim Confidential Report",
        "image_filename": "victim_rep.png",
        "ocr_text": "Net Qty 500ml MRP Rs 80",
        "extracted_data": {"net_quantity": "500ml", "mrp": "Rs 80"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T14:30:00Z",
        "owner_user_id": "p2b_rep_victim",
        "organization_id": "org_user_p2b_rep_victim"
    })

    resp = client.get(f"/api/report/{scan_id}/csv", headers={"Authorization": f"Bearer {token_intruder}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_09_public_user_cannot_access_merchant_data():
    """TEST 9: PUBLIC_USER cannot access merchant data."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_user_curious", pwh, salt, ROLE_USER)
    await create_user("p2b_merchant_corp", pwh, salt, ROLE_MERCHANT, organization_id="org_p2b_merchant_corp")
    token_user = create_token("p2b_user_curious", ROLE_USER)

    merch_scan = "p2b-corp-proprietary-item"
    await save_analysis({
        "id": merch_scan,
        "product_name": "Corporate Pre-market Formula",
        "image_filename": "corp_formula.png",
        "ocr_text": "Net Qty 2kg MRP Rs 999",
        "extracted_data": {"net_quantity": "2kg", "mrp": "Rs 999"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T15:00:00Z",
        "owner_user_id": "p2b_merchant_corp",
        "organization_id": "org_p2b_merchant_corp"
    })

    # User cannot open merchant scan
    resp_get = client.get(f"/api/history/{merch_scan}", headers={"Authorization": f"Bearer {token_user}"})
    assert resp_get.status_code == 403

    # User cannot delete merchant scan
    resp_del = client.delete(f"/api/history/{merch_scan}", headers={"Authorization": f"Bearer {token_user}"})
    assert resp_del.status_code == 403

    # User cannot download merchant report
    resp_rep = client.get(f"/api/report/{merch_scan}/csv", headers={"Authorization": f"Bearer {token_user}"})
    assert resp_rep.status_code == 403


@pytest.mark.asyncio
async def test_10_public_user_cannot_access_audit_data():
    """TEST 10: PUBLIC_USER cannot access audit review endpoints."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_normal_user_audit_check", pwh, salt, ROLE_USER)
    token_user = create_token("p2b_normal_user_audit_check", ROLE_USER)

    # Attempt to access officer reviews dashboard
    resp = client.get("/api/reviews/dashboard", headers={"Authorization": f"Bearer {token_user}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_11_public_user_cannot_access_enforcement_data():
    """TEST 11: PUBLIC_USER cannot access enforcement data."""
    client = TestClient(app)
    pwh, salt = hash_password("pass123")
    await create_user("p2b_user_enf_check", pwh, salt, ROLE_USER)
    await create_organization({"id": "org_enf_state", "name": "Enforcement Org", "status": "ACTIVE"})
    await create_user("p2b_officer_enf", pwh, salt, ROLE_ENFORCEMENT, organization_id="org_enf_state")

    token_user = create_token("p2b_user_enf_check", ROLE_USER)

    enf_scan = "p2b-confiscated-evidence-001"
    await save_analysis({
        "id": enf_scan,
        "product_name": "Seized Contraband Package",
        "image_filename": "seized.png",
        "ocr_text": "No Declarations",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "NON_COMPLIANT", "compliance_score": 0},
        "score": 0.0,
        "status": "NON_COMPLIANT",
        "created_at": "2026-09-18T16:00:00Z",
        "owner_user_id": "p2b_officer_enf",
        "organization_id": "org_enf_state"
    })

    resp = client.get(f"/api/history/{enf_scan}", headers={"Authorization": f"Bearer {token_user}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_12_merchant_workflow_remains_functional():
    """TEST 12: Merchant workflow remains functional."""
    client = TestClient(app)
    pwh, salt = hash_password("merchpass")
    await create_user("p2b_workflow_merchant", pwh, salt, ROLE_MERCHANT, organization_id="org_p2b_workflow_merchant")
    token_merch = create_token("p2b_workflow_merchant", ROLE_MERCHANT)

    scan_id = "p2b-merchant-workflow-scan"
    await save_analysis({
        "id": scan_id,
        "product_name": "Merchant Verified Juice",
        "image_filename": "juice.png",
        "ocr_text": "Net Qty 1L MRP Rs 110",
        "extracted_data": {"net_quantity": "1L", "mrp": "Rs 110"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T16:30:00Z",
        "owner_user_id": "p2b_workflow_merchant",
        "organization_id": "org_p2b_workflow_merchant"
    })

    # Stats
    resp_stats = client.get("/api/stats", headers={"Authorization": f"Bearer {token_merch}"})
    assert resp_stats.status_code == 200
    assert resp_stats.json()["total_analyzed"] >= 1

    # History
    resp_hist = client.get("/api/history", headers={"Authorization": f"Bearer {token_merch}"})
    assert resp_hist.status_code == 200
    assert any(item["id"] == scan_id for item in resp_hist.json())

    # Delete own
    resp_del = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_merch}"})
    assert resp_del.status_code == 200


@pytest.mark.asyncio
async def test_13_audit_officer_workflow_remains_functional():
    """TEST 13: Audit Officer workflow remains functional."""
    client = TestClient(app)
    pwh, salt = hash_password("auditpass")
    await create_organization({"id": "org_audit_zone", "name": "Audit Zone Org", "status": "ACTIVE"})
    await create_user("p2b_workflow_auditor", pwh, salt, ROLE_AUDIT, organization_id="org_audit_zone")
    token_audit = create_token("p2b_workflow_auditor", ROLE_AUDIT)

    resp_stats = client.get("/api/stats", headers={"Authorization": f"Bearer {token_audit}"})
    assert resp_stats.status_code == 200


@pytest.mark.asyncio
async def test_14_enforcement_officer_workflow_remains_functional():
    """TEST 14: Enforcement Officer workflow remains functional."""
    client = TestClient(app)
    pwh, salt = hash_password("enfpass")
    await create_organization({"id": "org_enf_zone", "name": "Enforcement Zone Org", "status": "ACTIVE"})
    await create_user("p2b_workflow_enforcer", pwh, salt, ROLE_ENFORCEMENT, organization_id="org_enf_zone")
    token_enf = create_token("p2b_workflow_enforcer", ROLE_ENFORCEMENT)

    scan_id = "p2b-enforcement-zone-scan"
    await save_analysis({
        "id": scan_id,
        "product_name": "Enforcement Case Item",
        "image_filename": "case_item.png",
        "ocr_text": "Net Qty 100g",
        "extracted_data": {"net_quantity": "100g"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "compliance_score": 100},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-18T17:00:00Z",
        "owner_user_id": "p2b_workflow_enforcer",
        "organization_id": "org_enf_zone"
    })

    # Enforcement Officer can delete within jurisdiction
    resp_del = client.delete(f"/api/history/{scan_id}", headers={"Authorization": f"Bearer {token_enf}"})
    assert resp_del.status_code == 200


@pytest.mark.asyncio
async def test_15_admin_workflow_remains_functional():
    """TEST 15: Admin workflow remains functional."""
    client = TestClient(app)
    pwh, salt = hash_password("adminpass")
    await create_user("p2b_super_admin", pwh, salt, ROLE_ADMIN, organization_id="org_ministry")
    token_admin = create_token("p2b_super_admin", ROLE_ADMIN)

    # Admin accesses users list
    resp_users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_users.status_code == 200
    assert isinstance(resp_users.json(), list)

    # Admin accesses officer requests
    resp_reqs = client.get("/api/admin/officer-requests", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_reqs.status_code == 200
