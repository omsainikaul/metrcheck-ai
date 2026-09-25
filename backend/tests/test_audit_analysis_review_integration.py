"""
Phase A-01.3: Integration Test Suite for Audit Analysis -> Officer Review Automatic Ingestion.

Verifies:
1. Audit analysis with REVIEW REQUIRED automatically creates exactly 1 officer_reviews record.
2. Review record contains correct analysis_id.
3. Review record contains correct organization_id (tenant preservation).
4. Review starts in PENDING_REVIEW state.
5. AI snapshot contains all qualifying compliance findings immutably.
6. Idempotency: re-running ingestion creates no duplicate reviews.
7. COMPLIANT analysis does not create mandatory review records.
8. POTENTIAL NON-COMPLIANCE / FAIL analysis creates review record.
9. Officer Review queue (GET /api/reviews/queue) returns the newly created review.
10. Cross-tenant isolation: Organization B cannot see Organization A reviews.
11. Consumer analysis does not enter Audit Officer (org_ministry) Review queue.
12. Merchant analysis does not enter Audit Officer (org_ministry) Review queue.
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app
from auth.security import create_token, hash_password, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT, ROLE_USER
from database.db import (
    init_db,
    create_user,
    save_analysis,
    get_analysis,
    get_review_by_analysis_id,
    list_reviews,
    get_review
)
from services.analysis_service import analyze_text, _auto_ingest_officer_review
from models.schemas import ProductInfo, ComplianceResult, ComplianceCheck

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database schema and seed tables are freshly initialized."""
    asyncio.run(init_db())


async def create_test_user(username: str, role: str, org_id: str = "org_ministry"):
    """Helper to create a user with specific organization."""
    salt, pwh = hash_password("TestPass123!")
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


def make_auth_header(username: str, role: str) -> dict:
    """Helper to generate JWT auth headers."""
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_01_audit_analysis_review_required_creates_single_review():
    """TEST 1: Audit analysis resulting in REVIEW REQUIRED automatically creates exactly 1 review record."""
    ana_id = "test-ana-audit-001"
    analysis_payload = {
        "id": ana_id,
        "product_name": "High Protein Oats",
        "image_filename": "oats.png",
        "ocr_text": "High Protein Oats Net Qty 500g",
        "score": 95.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_ministry",
        "owner_user_id": "audit_officer_1",
        "extracted_data": {"product_name": "High Protein Oats", "net_quantity": "500g"},
        "compliance_result": {
            "score": 95.0,
            "status": "REVIEW REQUIRED",
            "checks": [
                {
                    "rule_id": "LM-004",
                    "field": "mrp",
                    "field_label": "Maximum Retail Price (MRP)",
                    "status": "NEEDS_REVIEW",
                    "severity": "CRITICAL",
                    "reason": "MRP numeric price is faint in stamp area"
                }
            ],
            "risk_assessment": {"risk_level": "MEDIUM"}
        },
        "created_at": "2026-09-24T12:00:00Z"
    }

    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    rev = await get_review_by_analysis_id(ana_id)
    assert rev is not None, "Officer review record must be created for REVIEW REQUIRED analysis."
    assert rev["id"] == f"rev-{ana_id}"


@pytest.mark.asyncio
async def test_02_review_record_contains_correct_analysis_id():
    """TEST 2: Review record contains the exact matching analysis_id."""
    ana_id = "test-ana-audit-002"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Organic Honey",
        "score": 88.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_ministry",
        "owner_user_id": "audit_officer_1",
        "compliance_result": {"score": 88.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    rev = await get_review_by_analysis_id(ana_id)
    assert rev["analysis_id"] == ana_id


@pytest.mark.asyncio
async def test_03_review_record_contains_correct_organization_id():
    """TEST 3: Review record strictly inherits organization_id from analysis record."""
    ana_id = "test-ana-audit-003"
    org = "org_regional_audit_south"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Basmati Rice",
        "score": 85.0,
        "status": "REVIEW REQUIRED",
        "organization_id": org,
        "owner_user_id": "south_inspector_1",
        "compliance_result": {"score": 85.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    rev = await get_review_by_analysis_id(ana_id)
    assert rev["organization_id"] == org


@pytest.mark.asyncio
async def test_04_review_starts_in_pending_review_state():
    """TEST 4: New review record starts in PENDING_REVIEW state."""
    ana_id = "test-ana-audit-004"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Mustard Oil",
        "score": 75.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_ministry",
        "compliance_result": {"score": 75.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    rev = await get_review_by_analysis_id(ana_id)
    assert rev["status"] == "PENDING_REVIEW"
    assert rev["assigned_officer"] == ""


@pytest.mark.asyncio
async def test_05_ai_snapshot_contains_qualifying_findings():
    """TEST 5: AI snapshot preserves all compliance checks and review findings immutably."""
    ana_id = "test-ana-audit-005"
    checks_data = [
        {"rule_id": "LM-004", "field": "mrp", "status": "NEEDS_REVIEW", "severity": "CRITICAL", "reason": "Faint MRP"},
        {"rule_id": "FS-003", "field": "ingredients", "status": "NEEDS_REVIEW", "severity": "MAJOR", "reason": "Missing list"}
    ]
    analysis_payload = {
        "id": ana_id,
        "product_name": "Almond Cookies",
        "score": 90.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_ministry",
        "extracted_data": {"product_name": "Almond Cookies"},
        "compliance_result": {
            "score": 90.0,
            "status": "REVIEW REQUIRED",
            "checks": checks_data,
            "risk_assessment": {"risk_level": "MEDIUM"}
        }
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    rev = await get_review_by_analysis_id(ana_id)
    snap = json.loads(rev["ai_snapshot"])
    assert snap["score"] == 90.0
    assert snap["status"] == "REVIEW REQUIRED"
    assert len(snap["compliance_result"]["checks"]) == 2
    assert snap["compliance_result"]["checks"][0]["rule_id"] == "LM-004"


@pytest.mark.asyncio
async def test_06_idempotency_running_twice_creates_single_review():
    """TEST 6: Re-running ingestion hook multiple times creates exactly 1 review record."""
    ana_id = "test-ana-audit-006"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Green Tea",
        "score": 92.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_ministry",
        "compliance_result": {"score": 92.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)

    # Ingest 3 times consecutively
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    # Verify only 1 review in database
    reviews = await list_reviews(organization_id="org_ministry")
    matching = [r for r in reviews if r["analysis_id"] == ana_id]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_07_compliant_analysis_does_not_create_mandatory_review():
    """TEST 7: COMPLIANT analysis does NOT create an officer review task."""
    ana_id = "test-ana-audit-007"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Fully Compliant Salt",
        "score": 100.0,
        "status": "COMPLIANT",
        "organization_id": "org_ministry",
        "compliance_result": {"score": 100.0, "status": "COMPLIANT", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "COMPLIANT")

    rev = await get_review_by_analysis_id(ana_id)
    assert rev is None, "Compliant analysis must not create an officer review task."


@pytest.mark.asyncio
async def test_08_potential_non_compliance_creates_review():
    """TEST 8: POTENTIAL NON-COMPLIANCE / FAIL creates review record in PENDING_REVIEW."""
    ana_id = "test-ana-audit-008"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Misbranded Chips",
        "score": 45.0,
        "status": "POTENTIAL NON-COMPLIANCE",
        "organization_id": "org_ministry",
        "compliance_result": {
            "score": 45.0,
            "status": "POTENTIAL NON-COMPLIANCE",
            "checks": [
                {"rule_id": "LM-001", "field": "manufacturer", "status": "FAIL", "severity": "CRITICAL", "reason": "No manufacturer"}
            ],
            "risk_assessment": {"risk_level": "CRITICAL"}
        }
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "POTENTIAL NON-COMPLIANCE")

    rev = await get_review_by_analysis_id(ana_id)
    assert rev is not None
    assert rev["ai_status"] == "POTENTIAL NON-COMPLIANCE"
    assert rev["ai_risk_level"] == "CRITICAL"


@pytest.mark.asyncio
async def test_09_officer_review_queue_returns_created_review():
    """TEST 9: GET /api/reviews/queue returns the newly created review for authorized Audit Officer."""
    ana_id = "test-ana-audit-009"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Sunflower Oil 1L",
        "score": 91.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_ministry",
        "compliance_result": {"score": 91.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    await create_test_user("audit_officer_test", ROLE_AUDIT, "org_ministry")
    headers = make_auth_header("audit_officer_test", ROLE_AUDIT)
    resp = client.get("/api/reviews/queue", headers=headers)
    assert resp.status_code == 200
    queue = resp.json()
    review_ids = [it["analysis_id"] for it in queue]
    assert ana_id in review_ids


@pytest.mark.asyncio
async def test_10_cross_tenant_isolation_org_b_cannot_see_org_a_review():
    """TEST 10: Organization B officer cannot see Organization A review in their queue."""
    ana_id = "test-ana-org-a-010"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Org A Product",
        "score": 80.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_alpha",
        "compliance_result": {"score": 80.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    # Query from Org Beta officer
    await create_test_user("officer_beta", ROLE_AUDIT, "org_beta")
    headers_beta = make_auth_header("officer_beta", ROLE_AUDIT)
    resp_beta = client.get("/api/reviews/queue", headers=headers_beta)
    assert resp_beta.status_code == 200
    queue_beta = resp_beta.json()
    beta_ids = [it["analysis_id"] for it in queue_beta]
    assert ana_id not in beta_ids

    # Query from Org Alpha officer
    await create_test_user("officer_alpha", ROLE_AUDIT, "org_alpha")
    headers_alpha = make_auth_header("officer_alpha", ROLE_AUDIT)
    resp_alpha = client.get("/api/reviews/queue", headers=headers_alpha)
    assert resp_alpha.status_code == 200
    queue_alpha = resp_alpha.json()
    alpha_ids = [it["analysis_id"] for it in queue_alpha]
    assert ana_id in alpha_ids


@pytest.mark.asyncio
async def test_11_consumer_analysis_does_not_pollute_audit_officer_queue():
    """TEST 11: Consumer scans in personal consumer organization do not enter Audit Officer queue."""
    ana_id = "test-ana-consumer-011"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Consumer Scanned Snack",
        "score": 60.0,
        "status": "POTENTIAL NON-COMPLIANCE",
        "organization_id": "org_user_john_doe",
        "owner_user_id": "john_doe",
        "compliance_result": {"score": 60.0, "status": "POTENTIAL NON-COMPLIANCE", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "POTENTIAL NON-COMPLIANCE")

    # Audit Officer in org_ministry queries queue
    await create_test_user("audit_officer_gov", ROLE_AUDIT, "org_ministry")
    headers_audit = make_auth_header("audit_officer_gov", ROLE_AUDIT)
    resp = client.get("/api/reviews/queue", headers=headers_audit)
    assert resp.status_code == 200
    queue = resp.json()
    audit_ids = [it["analysis_id"] for it in queue]
    assert ana_id not in audit_ids, "Consumer analysis must not appear in Ministry Audit Officer queue."


@pytest.mark.asyncio
async def test_12_merchant_analysis_does_not_pollute_audit_officer_queue():
    """TEST 12: Merchant scans in merchant organization do not enter Audit Officer queue."""
    ana_id = "test-ana-merchant-012"
    analysis_payload = {
        "id": ana_id,
        "product_name": "Merchant Private SKU",
        "score": 70.0,
        "status": "REVIEW REQUIRED",
        "organization_id": "org_merchant_acme",
        "owner_user_id": "acme_merchant",
        "compliance_result": {"score": 70.0, "status": "REVIEW REQUIRED", "checks": []}
    }
    await save_analysis(analysis_payload)
    await _auto_ingest_officer_review(ana_id, "REVIEW REQUIRED")

    # Audit Officer in org_ministry queries queue
    await create_test_user("audit_officer_gov2", ROLE_AUDIT, "org_ministry")
    headers_audit = make_auth_header("audit_officer_gov2", ROLE_AUDIT)
    resp = client.get("/api/reviews/queue", headers=headers_audit)
    assert resp.status_code == 200
    queue = resp.json()
    audit_ids = [it["analysis_id"] for it in queue]
    assert ana_id not in audit_ids, "Merchant analysis must not appear in Ministry Audit Officer queue."

