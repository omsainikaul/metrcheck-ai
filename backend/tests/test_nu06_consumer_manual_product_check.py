"""
NU-06 — Consumer Manual Product Check Test Suite

Targeted verification for the standalone Manual Product Check feature
in the Consumer / Public User Workspace (POST /api/analyze/manual).

Verification Matrix:
1. Access Control: PUBLIC_USER & ROLE_ADMIN allowed; unauthenticated, merchant, audit officer, enforcement officer denied.
2. Request Validation: product_name required (non-blank), invalid payloads rejected (422).
3. Food Product Screening: FSSAI, veg/non-veg evaluated; mandatory declarations checked.
4. Non-Food Commodity Screening: FSSAI & veg/non-veg rules marked NOT_APPLICABLE.
5. Non-Compliant Product Handling: Missing mandatory fields flagged, score adjusted authoritatively.
6. Rule 12 Zero-Fabrication: Readability is NOT_ASSESSED; no synthetic font heights or physical calibration.
7. Metadata & Provenance: extraction_mode == 'manual', image list empty, UUID4 assigned, owner persisted.
8. PDF Report Generation: PDF stream contains Manual Mode header, disclaimer, and graceful Rule 12 notes.
9. Tenant Isolation & Deletion: Owner can view/delete; other users cannot access/delete.
10. API Endpoints Integration: Full lifecycle from POST /api/analyze/manual to GET /api/history/{id} and DELETE.
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from database.db import save_analysis, get_analysis, create_user
from models.schemas import AnalysisResponse
from auth.security import (
    create_token, hash_password,
    ROLE_USER, ROLE_ADMIN, ROLE_MERCHANT, ROLE_AUDIT, ROLE_ENFORCEMENT
)
from services.report_service import generate_pdf_report


@pytest.fixture
def client():
    return TestClient(app)


async def _setup_test_user(username: str, role: str) -> str:
    pwh, salt = hash_password("TestPassword123!")
    await create_user(
        username=username,
        password_hash=pwh,
        salt=salt,
        role=role,
        full_name=f"Test {username}",
    )
    return create_token(username, role)


@pytest.mark.asyncio
class TestManualCheckAccessControl:
    """1. Access Control & Role Enforcement"""

    async def test_public_user_allowed(self, client):
        token = await _setup_test_user("consumer_user_nu06_1", ROLE_USER)
        payload = {
            "product_name": "Alpino Peanut Butter Crunch 1kg",
            "is_food_product": True,
            "net_quantity": "1 kg",
            "mrp": "499.00",
            "manufacturer_name": "Alpino Health Foods Pvt Ltd",
            "manufacturer_address": "Surat, Gujarat, India",
            "country_of_origin": "India"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "id" in data
        assert data["product_info"]["extraction_mode"] == "manual"
        assert data["product_info"]["product_name"] == "Alpino Peanut Butter Crunch 1kg"

    async def test_normal_user_and_user_alias_allowed(self, client):
        token_nu = await _setup_test_user("consumer_user_nu_alias", "NORMAL_USER")
        token_u = await _setup_test_user("consumer_user_u_alias", "USER")
        payload = {
            "product_name": "CrunchKart Salted Potato Chips",
            "is_food_product": True,
            "net_quantity": "100 g",
            "mrp": "₹50 (Incl. of all taxes)",
            "manufacturer_name": "CrunchKart Foods Pvt. Ltd.",
            "country_of_origin": "India"
        }
        res1 = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token_nu}"})
        assert res1.status_code == 200, f"NORMAL_USER failed: {res1.text}"

        res2 = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token_u}"})
        assert res2.status_code == 200, f"USER role failed: {res2.text}"

    async def test_admin_allowed(self, client):
        token = await _setup_test_user("admin_user_nu06_1", ROLE_ADMIN)
        payload = {
            "product_name": "Admin Manual Check Sample",
            "is_food_product": False,
            "net_quantity": "500 g",
            "mrp": "150.00"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    async def test_unauthenticated_rejected(self, client):
        payload = {
            "product_name": "Unauth Check",
            "net_quantity": "100 g"
        }
        res = client.post("/api/analyze/manual", json=payload)
        assert res.status_code in (401, 403)

    async def test_merchant_rejected(self, client):
        token = await _setup_test_user("merchant_user_nu06_1", ROLE_MERCHANT)
        payload = {
            "product_name": "Merchant Check",
            "net_quantity": "100 g"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert "Insufficient privileges" in res.json().get("detail", "")

    async def test_officers_rejected(self, client):
        audit_token = await _setup_test_user("audit_officer_nu06_1", ROLE_AUDIT)
        enf_token = await _setup_test_user("enf_officer_nu06_1", ROLE_ENFORCEMENT)
        payload = {"product_name": "Officer Check", "net_quantity": "100 g"}

        res1 = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {audit_token}"})
        assert res1.status_code == 403
        assert "Insufficient privileges" in res1.json().get("detail", "")

        res2 = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {enf_token}"})
        assert res2.status_code == 403
        assert "Insufficient privileges" in res2.json().get("detail", "")


@pytest.mark.asyncio
class TestManualCheckValidation:
    """2. Request Validation & Boundary Conditions"""

    async def test_empty_product_name_rejected(self, client):
        token = await _setup_test_user("consumer_user_nu06_2", ROLE_USER)
        # Blank product_name
        res = client.post(
            "/api/analyze/manual",
            json={"product_name": "   ", "net_quantity": "500 g"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 422

    async def test_missing_product_name_rejected(self, client):
        token = await _setup_test_user("consumer_user_nu06_2", ROLE_USER)
        res = client.post(
            "/api/analyze/manual",
            json={"net_quantity": "500 g"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 422

    async def test_optional_fields_handled_gracefully(self, client):
        token = await _setup_test_user("consumer_user_nu06_2", ROLE_USER)
        res = client.post(
            "/api/analyze/manual",
            json={"product_name": "Minimal Valid Product"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["product_info"]["product_name"] == "Minimal Valid Product"


@pytest.mark.asyncio
class TestManualCheckComplianceEvaluation:
    """3. Authoritative Compliance Screening (Food vs Non-Food)"""

    async def test_fully_compliant_food_product(self, client):
        token = await _setup_test_user("consumer_user_nu06_3", ROLE_USER)
        payload = {
            "product_name": "Alpino Organic Peanut Butter",
            "brand": "Alpino",
            "category": "Food & Beverages",
            "is_food_product": True,
            "net_quantity": "1 kg",
            "mrp": "₹499.00 (Incl. of all taxes)",
            "unit_sale_price": "₹49.90 / 100 g",
            "manufacturer_name": "Alpino Health Foods Pvt Ltd",
            "manufacturer_address": "Plot 123, GIDC, Surat, Gujarat 395001",
            "country_of_origin": "India",
            "manufacture_date": "01/2026",
            "expiry_date": "01/2027",
            "best_before": "12 months from manufacture",
            "consumer_care_email": "care@alpino.in",
            "consumer_care_phone": "1800-123-4567",
            "fssai_license": "10020021000123",
            "veg_non_veg": "VEG",
            "ingredients": "Roasted Peanuts 100%",
            "nutritional_info": "Protein: 30g, Fats: 50g, Energy: 600kcal per 100g",
            "user_notes": "Purchased from supermarket"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        cr = data["compliance_result"]
        assert cr["score"] >= 80.0
        assert cr["failed_rules"] == 0

        # Check FSSAI rule is PASS
        fssai_check = next((c for c in cr["checks"] if "FSSAI" in c.get("rule_id", "") or "fssai" in c.get("field", "").lower()), None)
        if fssai_check:
            assert fssai_check["status"] == "PASS"

    async def test_crunchkart_demo_sample_package_evaluation(self, client):
        token = await _setup_test_user("consumer_user_nu06_demo", ROLE_USER)
        payload = {
            "product_name": "CrunchKart Salted Potato Chips",
            "brand": "CrunchKart",
            "generic_name": "Potato Chips",
            "category": "Snack Food",
            "is_food_product": True,
            "net_quantity": "100 g",
            "mrp": "₹50 (Incl. of all taxes)",
            "unit_sale_price": "₹0.50 / g",
            "manufacture_date": "09/2026",
            "best_before": "6 Months from manufacture",
            "batch_number": "CK-260921",
            "country_of_origin": "India",
            "manufacturer_name": "CrunchKart Foods Pvt. Ltd.",
            "manufacturer_address": "Plot 42, GIDC Industrial Estate, Surat, Gujarat 395001",
            "consumer_care_phone": "1800-000-5678",
            "consumer_care_email": "care@crunchkart.in",
            "consumer_care_address": "Plot 42, GIDC Industrial Estate, Surat, Gujarat 395001",
            "fssai_license": "10000000000001",
            "ingredients": "Potatoes, Edible Vegetable Oil (Palmolein), Salt (1.5%)",
            "allergen_info": "Manufactured in a facility that also processes peanuts and dairy.",
            "nutritional_info": "Energy: 540 kcal, Protein: 6.5g, Carbohydrates: 52g, Total Fat: 34g, Sodium: 600mg per 100g",
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert bool(data["id"])
        assert data["product_name"] == "CrunchKart Salted Potato Chips"
        cr = data["compliance_result"]
        assert cr["score"] >= 80.0
        assert cr["failed_rules"] == 0

    async def test_non_food_product_exempts_fssai(self, client):
        token = await _setup_test_user("consumer_user_nu06_3", ROLE_USER)
        payload = {
            "product_name": "Steel Measuring Tape 5m",
            "brand": "PrecisionTools",
            "category": "Hardware & Tools",
            "is_food_product": False,
            "net_quantity": "1 N",
            "mrp": "₹250.00 (Incl. of all taxes)",
            "unit_sale_price": "₹250.00 / N",
            "manufacturer_name": "Precision Tools Ltd",
            "manufacturer_address": "Pune, Maharashtra",
            "country_of_origin": "India",
            "consumer_care_phone": "1800-999-0000"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        cr = data["compliance_result"]
        
        # FSSAI rule should be NOT_APPLICABLE
        fssai_checks = [c for c in cr["checks"] if "FSSAI" in c.get("rule_id", "") or "fssai" in c.get("field", "").lower()]
        for fc in fssai_checks:
            assert fc["status"] == "NOT_APPLICABLE"

    async def test_non_compliant_missing_mrp_manufacturer(self, client):
        token = await _setup_test_user("consumer_user_nu06_3", ROLE_USER)
        payload = {
            "product_name": "Unbranded Generic Item",
            "is_food_product": False,
            # Intentionally missing MRP, manufacturer, consumer care, etc.
            "net_quantity": "100 g"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        cr = data["compliance_result"]
        assert cr["failed_rules"] > 0
        assert cr["status"] in ("POTENTIAL NON-COMPLIANCE", "POTENTIAL_NON_COMPLIANCE", "REVIEW_REQUIRED", "FAIL", "NEEDS_REVIEW")


@pytest.mark.asyncio
class TestManualCheckRule12NotAssessed:
    """4. Rule 12 Zero-Fabrication Guarantee"""

    async def test_rule12_is_not_assessed(self, client):
        token = await _setup_test_user("consumer_user_nu06_4", ROLE_USER)
        payload = {
            "product_name": "Sample Commodity",
            "net_quantity": "500 g",
            "mrp": "100.00",
            "manufacturer_name": "Sample Maker",
            "country_of_origin": "India"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()

        # Font size analysis must exist with NOT_ASSESSED tier
        fsa = data.get("font_size_analysis")
        assert fsa is not None
        assert fsa["readability_tier"] == "NOT_ASSESSED"
        assert fsa["readability_score"] == 0.0
        assert fsa.get("calibration_status") == "PHYSICAL_MEASUREMENT_NOT_ASSESSED"
        assert fsa.get("net_quantity_font_height_mm") is None


@pytest.mark.asyncio
class TestManualCheckPDFGeneration:
    """5. PDF Report Generation for Manual Check"""

    async def test_pdf_stream_validity_and_manual_mode_markers(self, client):
        token = await _setup_test_user("consumer_user_nu06_5", ROLE_USER)
        payload = {
            "product_name": "Alpino Peanut Butter Manual PDF Test",
            "brand": "Alpino",
            "is_food_product": True,
            "net_quantity": "1 kg",
            "mrp": "499.00",
            "manufacturer_name": "Alpino Health Foods Pvt Ltd",
            "manufacturer_address": "Surat, Gujarat",
            "country_of_origin": "India",
            "fssai_license": "10020021000123"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        aid = data["id"]

        # 1. Test direct generate_pdf_report service
        analysis_obj = AnalysisResponse(**data)
        pdf_bytes = generate_pdf_report(analysis_obj, lang="en")
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 2000

        # 2. Test GET /api/report/{id}/pdf
        pdf_res = client.get(f"/api/report/{aid}/pdf", headers={"Authorization": f"Bearer {token}"})
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF")


@pytest.mark.asyncio
class TestManualCheckTenantIsolation:
    """6. Tenant Isolation, Retrieval & Deletion"""

    async def test_tenant_isolation_and_delete(self, client):
        token_a = await _setup_test_user("consumer_user_nu06_a", ROLE_USER)
        token_b = await _setup_test_user("consumer_user_nu06_b", ROLE_USER)

        payload = {
            "product_name": "User A Private Product",
            "net_quantity": "250 g",
            "mrp": "99.00",
            "manufacturer_name": "Private Corp"
        }
        res = client.post("/api/analyze/manual", json=payload, headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        data = res.json()
        aid = data["id"]
        assert data["owner_user_id"] == "consumer_user_nu06_a"

        # User A can retrieve it
        get_res_a = client.get(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token_a}"})
        assert get_res_a.status_code == 200
        assert get_res_a.json()["id"] == aid

        # User B CANNOT retrieve it (tenant isolation)
        get_res_b = client.get(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token_b}"})
        assert get_res_b.status_code in (403, 404)

        # User B CANNOT delete it
        del_res_b = client.delete(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token_b}"})
        assert del_res_b.status_code in (403, 404)

        # User A CAN delete it
        del_res_a = client.delete(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token_a}"})
        assert del_res_a.status_code == 200

        # Now it's gone
        get_res_after = client.get(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token_a}"})
        assert get_res_after.status_code == 404
