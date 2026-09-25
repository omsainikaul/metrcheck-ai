"""
MetrCheck AI — Test Suite E-01: Enforcement Officer Assignment & Case-Linkage

Validates:
A. Audit review assignment to Audit Officer
B. Enforcement Officer cannot improperly receive an Audit Review (backend rejection)
C. Audit escalation creates an Enforcement Case (enforcement_cases record with case_reference)
D. Enforcement Case links to officer_review (review_id)
E. Enforcement Case links to analysis (analysis_id)
F. Enforcement Case preserves organization_id
G. Enforcement Case can be assigned to Enforcement Officer (via POST /api/enforcement/cases/{case_id}/assign)
H. Assigned Enforcement Officer sees the case in docket and dashboard
I. Unassigned Enforcement Officer does not see another officer's private "Assigned To Me" workload
J. Cross-tenant Enforcement Case access returns 403
K. Duplicate active enforcement case remains prevented on subsequent escalation
L. Existing state transitions remain valid
M. Existing Audit Officer workflows remain functional
N. Existing Enforcement Officer workflows remain functional
Exact End-to-End Scenario:
  Officer Review -> Escalate -> Enforcement Case created -> Assign to Krish (ENFORCEMENT_OFFICER) -> Login/use Enforcement Workspace as Krish -> Case appears in Assigned To Me
"""

import pytest
import asyncio
import json
import uuid
from fastapi.testclient import TestClient

from main import app
from auth.security import hash_password, create_token, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT, ROLE_USER
from database.db import (
    init_db,
    create_organization,
    create_user,
    save_analysis,
    get_analysis,
    save_review,
    get_review,
    get_enforcement_case,
    get_enforcement_case_by_analysis_id,
    list_enforcement_cases,
    get_enforcement_dashboard_metrics,
    get_user_by_username
)
from services.review_service import get_or_create_review

client = TestClient(app)


async def _create_test_user(username: str, role: str, org_id: str = "", state: str = "Delhi", district: str = "Central"):
    salt, pwh = hash_password("Password123!")
    try:
        await create_user(
            username=username,
            password_hash=pwh,
            salt=salt,
            role=role,
            full_name=f"User {username}",
            organization_id=org_id,
            jurisdiction=f"{state} - {district}"
        )
    except Exception:
        pass


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database schema and test users are initialized before every test."""
    async def _init():
        await init_db()
        await create_organization("org_ministry", "Ministry of Consumer Affairs", org_type="REGULATOR", jurisdiction="National")
        await create_organization("org_state_delhi", "Delhi Legal Metrology Dept", org_type="REGULATOR", jurisdiction="Delhi")
        await create_organization("org_state_maharashtra", "Maharashtra Legal Metrology Dept", org_type="REGULATOR", jurisdiction="Maharashtra")
        await _create_test_user("admin", ROLE_ADMIN, "org_ministry")
        await _create_test_user("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
        await _create_test_user("off_lm_demo_dl_2026_010", ROLE_ENFORCEMENT, "org_ministry")
        await _create_test_user("officer", ROLE_ENFORCEMENT, "org_ministry")
        await _create_test_user("officer_delhi", ROLE_ENFORCEMENT, "org_state_delhi")
        await _create_test_user("officer_mumbai", ROLE_ENFORCEMENT, "org_state_maharashtra")

    asyncio.run(_init())


def make_auth_header(username: str, role: str, org_id: str = "org_ministry") -> dict:
    """Helper to generate JWT header."""
    token = create_token(username, role)
    return {"Authorization": f"Bearer {token}"}


def create_mock_analysis_dict(ana_id: str, product_name: str = "High Protein Oats", org_id: str = "org_ministry") -> dict:
    """Generates an analysis record with non-compliant statutory declarations."""
    return {
        "id": ana_id,
        "product_name": product_name,
        "image_filename": f"{ana_id}_front.jpg",
        "ocr_text": f"{product_name} 500g MRP Rs 120 Mfg by Healthy Foods Ltd",
        "score": 65.0,
        "status": "NON_COMPLIANT",
        "organization_id": org_id,
        "created_at": "2026-09-24T10:00:00Z",
        "extracted_data": json.dumps({
            "product_name": product_name,
            "net_quantity": "500g",
            "mrp": "Rs 120",
            "manufacturer": "Healthy Foods Ltd"
        }),
        "compliance_result": json.dumps({
            "score": 65.0,
            "status": "FAIL",
            "risk_assessment": {"risk_level": "CRITICAL"},
            "checks": [
                {
                    "rule_id": "LM_MRP_01",
                    "field": "mrp",
                    "field_label": "Maximum Retail Price",
                    "status": "FAIL",
                    "severity": "critical",
                    "reason": "Missing Unit Sale Price declaration under Rule 6(1)(e)."
                },
                {
                    "rule_id": "LM_ORIGIN_01",
                    "field": "country_of_origin",
                    "field_label": "Country of Origin",
                    "status": "FAIL",
                    "severity": "critical",
                    "reason": "Country of origin is not declared on the principal display panel."
                }
            ]
        })
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test A & B: Review Assignment Role Separation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_review_assignment_to_audit_officer():
    """Test A: Audit review can be successfully assigned to an AUDIT_OFFICER."""
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id)
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    payload = {
        "assigned_officer": "audit_lm_demo_dl_2026_002",
        "comments": "Assigning package review for verification"
    }
    resp = client.post(f"/api/reviews/{review['id']}/assign", json=payload, headers=audit_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["assigned_officer"] == "audit_lm_demo_dl_2026_002"
    assert data["new_status"] == "ASSIGNED"


@pytest.mark.asyncio
async def test_enforcement_officer_cannot_receive_audit_review():
    """Test B: Assigning an ENFORCEMENT_OFFICER to an Audit Review is rejected by backend."""
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id)
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    # Attempt to assign review to Krish (ENFORCEMENT_OFFICER)
    payload = {
        "assigned_officer": "off_lm_demo_dl_2026_010",
        "comments": "Invalid assignment attempt"
    }
    resp = client.post(f"/api/reviews/{review['id']}/assign", json=payload, headers=audit_headers)
    assert resp.status_code == 400
    assert "Audit reviews can only be assigned to AUDIT_OFFICER or ADMIN" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_officers_endpoint_returns_only_audit_eligible():
    """Verify GET /api/reviews/officers does NOT include ENFORCEMENT_OFFICER accounts."""
    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    resp = client.get("/api/reviews/officers", headers=audit_headers)
    assert resp.status_code == 200
    officers = resp.json()["officers"]
    
    # Verify all returned officers have role AUDIT_OFFICER or ADMIN
    for off in officers:
        assert off["role"] in (ROLE_ADMIN, ROLE_AUDIT), f"Invalid role {off['role']} in audit officers endpoint"
    
    # Explicitly ensure enforcement officer Krish is NOT in the audit review officers list
    usernames = [o["username"] for o in officers]
    assert "off_lm_demo_dl_2026_010" not in usernames


# ─────────────────────────────────────────────────────────────────────────────
# Test C, D, E, F, K: Audit Escalation -> Enforcement Case Creation & Linkage
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_escalation_creates_and_links_enforcement_case():
    """
    Test C, D, E, F: Escalation creates an Enforcement Case with proper linkages:
    - analysis_id
    - review_id
    - organization_id
    - case_reference
    - audit timeline
    """
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "High Protein Oats", "org_ministry")
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    esc_payload = {
        "escalation_reason": "CRITICAL_STATUTORY_VIOLATION",
        "comments": "Missing Unit Sale Price and Country of Origin declarations require formal enforcement notice."
    }
    resp = client.post(f"/api/reviews/{review['id']}/escalate", json=esc_payload, headers=audit_headers)
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "ESCALATED"

    # Verify enforcement case was created
    case = await get_enforcement_case_by_analysis_id(ana_id)
    assert case is not None
    assert case["analysis_id"] == ana_id
    assert case["review_id"] == review["id"]
    assert case["organization_id"] == "org_ministry"
    assert case["product_name"] == "High Protein Oats"
    assert case["status"] == "OPEN"
    assert case["severity"] in ("CRITICAL", "HIGH")
    assert case["case_reference"].startswith("MC-ENF-")
    assert "Escalated from Audit Review" in case["violation_summary"]
    assert len(case["timeline"]) >= 1
    assert case["timeline"][0]["action"] == "CASE_CREATED"


@pytest.mark.asyncio
async def test_duplicate_active_enforcement_case_prevention():
    """Test K: Re-escalating an already escalated review does not produce duplicate active cases."""
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "High Protein Oats", "org_ministry")
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    esc_payload = {
        "escalation_reason": "CRITICAL_STATUTORY_VIOLATION",
        "comments": "First escalation."
    }
    resp1 = client.post(f"/api/reviews/{review['id']}/escalate", json=esc_payload, headers=audit_headers)
    assert resp1.status_code == 200

    # Capture case reference
    case1 = await get_enforcement_case_by_analysis_id(ana_id)
    assert case1 is not None

    # Count total cases before
    cases_before, count_before = await list_enforcement_cases(organization_id="org_ministry")

    # Second escalation attempt
    esc_payload2 = {
        "escalation_reason": "REPEATED_AUDIT_FINDING",
        "comments": "Second escalation check."
    }
    # Reopen first to allow transition to ESCALATED again
    admin_headers = make_auth_header("admin", ROLE_ADMIN, "org_ministry")
    client.post(f"/api/reviews/{review['id']}/reopen", json={"reopen_reason": "Re-check"}, headers=admin_headers)
    client.post(f"/api/reviews/{review['id']}/escalate", json=esc_payload2, headers=audit_headers)

    cases_after, count_after = await list_enforcement_cases(organization_id="org_ministry")
    assert count_after == count_before, "Duplicate enforcement case was erroneously created!"


# ─────────────────────────────────────────────────────────────────────────────
# Test G, H, I, J: Enforcement Officer Assignment & Workload Visibility
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enforcement_case_assignment_and_visibility():
    """
    Test G & H: Enforcement case can be assigned to an ENFORCEMENT_OFFICER (Krish)
    and appears in Assigned To Me filter and dashboard KPI.
    """
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "High Protein Oats", "org_ministry")
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    # 1. Audit Officer escalates
    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    client.post(
        f"/api/reviews/{review['id']}/escalate",
        json={"escalation_reason": "STATUTORY_NON_COMPLIANCE"},
        headers=audit_headers
    )

    case = await get_enforcement_case_by_analysis_id(ana_id)
    assert case is not None
    assert case["assigned_officer"] == ""

    # 2. Enforcement Officer (or Admin) assigns the case to Krish
    enf_headers = make_auth_header("off_lm_demo_dl_2026_010", ROLE_ENFORCEMENT, "org_ministry")
    assign_payload = {
        "assigned_officer": "off_lm_demo_dl_2026_010",
        "comments": "Assigned to investigating officer Krish for statutory notice drafting."
    }
    assign_resp = client.post(
        f"/api/enforcement/cases/{case['id']}/assign",
        json=assign_payload,
        headers=enf_headers
    )
    assert assign_resp.status_code == 200
    case_detail = assign_resp.json()
    assert case_detail["assigned_officer"] == "off_lm_demo_dl_2026_010"

    # 3. Krish inspects Enforcement Dashboard & Docket
    dash_resp = client.get("/api/enforcement/dashboard", headers=enf_headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["assigned_to_me"] >= 1

    # 4. Krish inspects list filtered to assigned_officer="off_lm_demo_dl_2026_010"
    list_resp = client.get(
        "/api/enforcement/cases?assigned_officer=off_lm_demo_dl_2026_010",
        headers=enf_headers
    )
    assert list_resp.status_code == 200
    found_cases = list_resp.json()["cases"]
    assert any(c["id"] == case["id"] for c in found_cases)


@pytest.mark.asyncio
async def test_unassigned_enforcement_officer_isolation():
    """Test I: Another officer's assigned_to_me count does not leak to a different officer."""
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "High Protein Oats", "org_ministry")
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    client.post(
        f"/api/reviews/{review['id']}/escalate",
        json={"escalation_reason": "STATUTORY_NON_COMPLIANCE"},
        headers=audit_headers
    )
    case = await get_enforcement_case_by_analysis_id(ana_id)

    # Assign specifically to Krish
    admin_headers = make_auth_header("admin", ROLE_ADMIN, "org_ministry")
    client.post(
        f"/api/enforcement/cases/{case['id']}/assign",
        json={"assigned_officer": "off_lm_demo_dl_2026_010"},
        headers=admin_headers
    )

    # Check from perspective of another enforcement officer ("officer")
    other_enf_headers = make_auth_header("officer", ROLE_ENFORCEMENT, "org_ministry")
    other_list = client.get(
        "/api/enforcement/cases?assigned_officer=officer",
        headers=other_enf_headers
    ).json()["cases"]
    assert not any(c["id"] == case["id"] for c in other_list)


@pytest.mark.asyncio
async def test_cross_tenant_enforcement_case_access_blocked():
    """Test J: Cross-tenant access to enforcement cases returns 403 Forbidden."""
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "Tenant A Oats", "org_state_delhi")
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    # Escalate within org_state_delhi
    delhi_headers = make_auth_header("officer_delhi", ROLE_ENFORCEMENT, "org_state_delhi")
    client.post(
        f"/api/reviews/{review['id']}/escalate",
        json={"escalation_reason": "STATE_JURISDICTION_ACTION"},
        headers=delhi_headers
    )
    case = await get_enforcement_case_by_analysis_id(ana_id)
    assert case is not None

    # Attempt access from officer in org_state_maharashtra
    mumbai_headers = make_auth_header("officer_mumbai", ROLE_ENFORCEMENT, "org_state_maharashtra")
    resp = client.get(f"/api/enforcement/cases/{case['id']}", headers=mumbai_headers)
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Test L, M, N: Full Enforcement Case Lifecycle & State Machine
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enforcement_state_transitions_and_workflows():
    """
    Test L, M, N: Complete lifecycle transitions:
    OPEN -> INVESTIGATION -> PENALTY_REVIEW -> NOTICE_ISSUED -> HEARING -> RESOLVED -> CLOSED
    """
    ana_id = f"test-ana-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "High Protein Oats", "org_ministry")
    await save_analysis(analysis)
    review = await get_or_create_review(ana_id)

    # 1. Audit escalation
    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    client.post(
        f"/api/reviews/{review['id']}/escalate",
        json={"escalation_reason": "MANDATORY_STATUTORY_ENFORCEMENT"},
        headers=audit_headers
    )
    case = await get_enforcement_case_by_analysis_id(ana_id)
    case_id = case["id"]

    enf_headers = make_auth_header("off_lm_demo_dl_2026_010", ROLE_ENFORCEMENT, "org_ministry")

    # 2. Assign to Krish
    client.post(
        f"/api/enforcement/cases/{case_id}/assign",
        json={"assigned_officer": "off_lm_demo_dl_2026_010"},
        headers=enf_headers
    )

    # 3. Transition: OPEN -> INVESTIGATION
    t_resp = client.post(
        f"/api/enforcement/cases/{case_id}/transition",
        json={"to_status": "INVESTIGATION", "reason": "Commencing on-site evidence verification."},
        headers=enf_headers
    )
    assert t_resp.status_code == 200
    assert t_resp.json()["status"] == "INVESTIGATION"

    # 4. Calculate Penalty -> Transitions to PENALTY_REVIEW
    p_resp = client.post(
        f"/api/enforcement/cases/{case_id}/calculate-penalty",
        json={"repeat_offence": False, "prior_notices": 0, "reason": "Section 36 evaluation"},
        headers=enf_headers
    )
    assert p_resp.status_code == 200
    assert p_resp.json()["estimated_fine_inr"] > 0

    c_detail = client.get(f"/api/enforcement/cases/{case_id}", headers=enf_headers).json()
    assert c_detail["status"] == "PENALTY_REVIEW"

    # 5. Issue SCN Notice -> Transitions to NOTICE_ISSUED
    n_resp = client.post(
        f"/api/enforcement/cases/{case_id}/notices",
        json={
            "notice_type": "SHOW_CAUSE",
            "officer_name": "Krish Verma",
            "officer_designation": "Legal Metrology Inspector",
            "deadline_days": 15
        },
        headers=enf_headers
    )
    assert n_resp.status_code == 201
    assert n_resp.json()["notice_reference"].startswith("MC-SCN-")

    c_detail = client.get(f"/api/enforcement/cases/{case_id}", headers=enf_headers).json()
    assert c_detail["status"] == "NOTICE_ISSUED"

    # 6. Transition: NOTICE_ISSUED -> HEARING
    h_resp = client.post(
        f"/api/enforcement/cases/{case_id}/transition",
        json={"to_status": "HEARING", "reason": "Manufacturer requested compounding hearing."},
        headers=enf_headers
    )
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "HEARING"

    # 7. Transition: HEARING -> RESOLVED
    r_resp = client.post(
        f"/api/enforcement/cases/{case_id}/transition",
        json={"to_status": "RESOLVED", "reason": "Compounding fee accepted and paid."},
        headers=enf_headers
    )
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "RESOLVED"

    # 8. Close case
    cl_resp = client.post(
        f"/api/enforcement/cases/{case_id}/close",
        json={"closure_reason": "Proceedings compounded and fine collected in full.", "resolution_type": "COMPOUNDED"},
        headers=enf_headers
    )
    assert cl_resp.status_code == 200
    assert cl_resp.json()["status"] == "CLOSED"
    assert cl_resp.json()["closed_at"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Exact End-to-End Scenario: High Protein Oats
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exact_high_protein_oats_workflow_scenario():
    """
    Exact scenario from user prompt:
    Officer Review (High Protein Oats)
        ↓
    Audit Officer Escalate
        ↓
    Enforcement Case created
        ↓
    Assign to Krish (ENFORCEMENT_OFFICER)
        ↓
    Login/use Enforcement Workspace as Krish
        ↓
    Case appears in Assigned To Me
    """
    ana_id = f"hpo-test-{uuid.uuid4().hex[:8]}"
    analysis = create_mock_analysis_dict(ana_id, "High Protein Oats", "org_ministry")
    await save_analysis(analysis)

    # 1. Automatic Ingestion into Officer Review
    review = await get_or_create_review(ana_id)
    assert review is not None
    assert review["status"] == "PENDING_REVIEW"

    # 2. Audit Officer inspects and escalates
    audit_headers = make_auth_header("audit_lm_demo_dl_2026_002", ROLE_AUDIT, "org_ministry")
    esc_res = client.post(
        f"/api/reviews/{review['id']}/escalate",
        json={
            "escalation_reason": "MISSING_MANDATORY_STATUTORY_DECLARATIONS",
            "comments": "High Protein Oats missing USP and origin declarations. Escalated for legal enforcement."
        },
        headers=audit_headers
    )
    assert esc_res.status_code == 200

    # 3. Verify Enforcement Case exists in DB
    enf_case = await get_enforcement_case_by_analysis_id(ana_id)
    assert enf_case is not None
    assert enf_case["product_name"] == "High Protein Oats"
    assert enf_case["status"] == "OPEN"

    # 4. Assign Enforcement Case to Krish (off_lm_demo_dl_2026_010)
    admin_or_enf_headers = make_auth_header("admin", ROLE_ADMIN, "org_ministry")
    assign_res = client.post(
        f"/api/enforcement/cases/{enf_case['id']}/assign",
        json={
            "assigned_officer": "off_lm_demo_dl_2026_010",
            "comments": "Assigned to Inspector Krish for immediate notice issuance."
        },
        headers=admin_or_enf_headers
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_officer"] == "off_lm_demo_dl_2026_010"

    # 5. Krish accesses Enforcement Workspace
    krish_headers = make_auth_header("off_lm_demo_dl_2026_010", ROLE_ENFORCEMENT, "org_ministry")
    
    # Dashboard check: assigned_to_me reflects the new case
    dash_res = client.get("/api/enforcement/dashboard", headers=krish_headers)
    assert dash_res.status_code == 200
    assert dash_res.json()["assigned_to_me"] >= 1
    assert dash_res.json()["total_active_cases"] >= 1

    # Case list filtered to Assigned To Me
    list_res = client.get(
        "/api/enforcement/cases?assigned_officer=off_lm_demo_dl_2026_010",
        headers=krish_headers
    )
    assert list_res.status_code == 200
    krish_cases = list_res.json()["cases"]
    matching = [c for c in krish_cases if c["id"] == enf_case["id"]]
    assert len(matching) == 1
    assert matching[0]["product_name"] == "High Protein Oats"
    assert matching[0]["assigned_officer"] == "off_lm_demo_dl_2026_010"
