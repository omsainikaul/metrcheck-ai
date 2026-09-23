"""
Phase 4C Test Suite 2: Jurisdiction Security & Multi-Authority Scope Testing
Verifies the authoritative jurisdiction model:
- Regulatory Authority Organization (Tenant) Boundary
- State & District metadata classification and server-side filtering
- Tamper-proofing against parameter injection (?district=, ?state=, ?merchant_organization_id=)
- Dashboard metric isolation across distinct enforcement organizations
"""
import os
import json
import pytest
from fastapi.testclient import TestClient

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import (
    get_db,
    init_db,
    create_organization,
    create_user,
    save_analysis,
    save_enforcement_case,
    get_enforcement_case,
    save_penalty_calculation,
    save_enforcement_notice
)
from auth.security import (
    hash_password,
    create_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT
)


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "CRITICAL: Running on prod DB!"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "CRITICAL: Running on prod upload dir!"


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


def make_headers(username: str, role: str, token_version: int = 1) -> dict:
    token = create_token(username, role, token_version=token_version)
    return {"Authorization": f"Bearer {token}"}


async def _seed_jurisdiction_data():
    await init_db()
    db = await get_db()
    try:
        await db.execute("DELETE FROM enforcement_notices")
        await db.execute("DELETE FROM penalty_calculations")
        await db.execute("DELETE FROM enforcement_cases")
        await db.commit()
    finally:
        await db.close()

    # Create distinct State Enforcement Organizations
    await create_organization("org_jur_delhi", "Delhi Legal Metrology Department", org_type="REGULATOR", jurisdiction="Delhi")
    await create_organization("org_jur_maharashtra", "Maharashtra Legal Metrology Department", org_type="REGULATOR", jurisdiction="Maharashtra")
    await create_organization("org_jur_karnataka", "Karnataka Legal Metrology Department", org_type="REGULATOR", jurisdiction="Karnataka")

    # Officers in distinct authorities
    await _create_test_user("jur_admin", ROLE_ADMIN, "")
    await _create_test_user("jur_delhi_officer_1", ROLE_ENFORCEMENT, "org_jur_delhi", state="Delhi", district="Central")
    await _create_test_user("jur_delhi_officer_2", ROLE_ENFORCEMENT, "org_jur_delhi", state="Delhi", district="South")
    await _create_test_user("jur_maha_officer_1", ROLE_ENFORCEMENT, "org_jur_maharashtra", state="Maharashtra", district="Mumbai")
    await _create_test_user("jur_karn_officer_1", ROLE_ENFORCEMENT, "org_jur_karnataka", state="Karnataka", district="Bengaluru")

    # Seed analysis records
    await save_analysis({
        "id": "ana_jur_delhi_1",
        "product_name": "Delhi Spices Pack 100g",
        "owner_user_id": "jur_delhi_officer_1",
        "organization_id": "org_jur_delhi",
        "score": 50.0,
        "status": "FAIL",
        "compliance_result": json.dumps({"score": 50.0, "status": "FAIL", "checks": [{"field": "mrp", "status": "FAIL", "rule_id": "Rule 6(1)(e)"}]})
    })

    await save_analysis({
        "id": "ana_jur_delhi_2",
        "product_name": "Delhi Ghee 500ml",
        "owner_user_id": "jur_delhi_officer_2",
        "organization_id": "org_jur_delhi",
        "score": 45.0,
        "status": "FAIL",
        "compliance_result": json.dumps({"score": 45.0, "status": "FAIL", "checks": [{"field": "net_quantity", "status": "FAIL", "rule_id": "Rule 11"}]})
    })

    await save_analysis({
        "id": "ana_jur_maha_1",
        "product_name": "Mumbai Wafer Chips 200g",
        "owner_user_id": "jur_maha_officer_1",
        "organization_id": "org_jur_maharashtra",
        "score": 40.0,
        "status": "FAIL",
        "compliance_result": json.dumps({"score": 40.0, "status": "FAIL", "checks": [{"field": "mrp", "status": "FAIL", "rule_id": "Rule 6(1)(e)"}]})
    })


# ═════════════════════════════════════════════════════════════════════════════
# 1. JURISDICTION ISOLATION & PERMITTED ACCESS (Requirements 5 & 6)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_01_authorized_jurisdiction_case_access():
    """Test 1: Officer from authorized jurisdiction accesses permitted case."""
    await _seed_jurisdiction_data()
    client = TestClient(app)
    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)

    # Create Delhi case
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1", "severity": "CRITICAL"}, headers=headers_delhi)
    assert r_create.status_code == 201
    case_id = r_create.json()["id"]

    # Read case by officer in same authority
    r_get = client.get(f"/api/enforcement/cases/{case_id}", headers=headers_delhi)
    assert r_get.status_code == 200
    assert r_get.json()["jurisdiction_state"] == "Delhi"


@pytest.mark.asyncio
async def test_02_unauthorized_jurisdiction_case_access():
    """Test 2: Officer from unauthorized jurisdiction attempts access (rejected 403)."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Delhi officer creates Delhi case
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    case_delhi_id = r_create.json()["id"]

    # Maharashtra officer attempts to access Delhi case
    headers_maha = make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT)
    r_bad = client.get(f"/api/enforcement/cases/{case_delhi_id}", headers=headers_maha)
    assert r_bad.status_code == 403


@pytest.mark.asyncio
async def test_03_request_body_jurisdiction_override_tamper_proofing():
    """Test 3 & 5: Officer attempts to manipulate jurisdiction fields in request body."""
    await _seed_jurisdiction_data()
    client = TestClient(app)
    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)

    # Delhi officer tries to create case referencing Maharashtra analysis by claiming Maharashtra jurisdiction
    payload = {
        "analysis_id": "ana_jur_maha_1",
        "jurisdiction_state": "Maharashtra",
        "jurisdiction_district": "Mumbai"
    }
    r = client.post("/api/enforcement/cases", json=payload, headers=headers_delhi)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_04_query_parameter_jurisdiction_tamper_proofing():
    """Test 4: Attempt jurisdiction override through query parameters."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Delhi officer creates Delhi case
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    # Maharashtra officer creates Maharashtra case
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_maha_1"}, headers=make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT))

    # Delhi officer tries to list cases passing ?jurisdiction_state=Maharashtra
    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_list = client.get("/api/enforcement/cases?jurisdiction_state=Maharashtra", headers=headers_delhi)
    assert r_list.status_code == 200
    # Must NOT return Maharashtra cases (returns empty list because Delhi org has no cases in Maharashtra)
    assert r_list.json()["total"] == 0


@pytest.mark.asyncio
async def test_05_merchant_organization_query_tamper_proofing():
    """Attempt merchant organization override through query parameters."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Seed cases
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_maha_1"}, headers=make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT))

    # Delhi officer tries ?merchant_organization_id=org_jur_maharashtra
    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_list = client.get("/api/enforcement/cases?merchant_organization_id=org_jur_maharashtra", headers=headers_delhi)
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 0


@pytest.mark.asyncio
async def test_06_dashboard_aggregation_jurisdiction_isolation():
    """Test 7 & 8: Dashboard aggregation strictly scopes metrics, notices, and fine totals to authority."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Delhi: 1 case with penalty and notice
    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_d = client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=headers_delhi)
    d_case_id = r_d.json()["id"]
    client.post(f"/api/enforcement/cases/{d_case_id}/calculate-penalty", json={}, headers=headers_delhi)
    client.post(f"/api/enforcement/cases/{d_case_id}/notices", json={}, headers=headers_delhi)

    # Maharashtra: 1 case with penalty and notice
    headers_maha = make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT)
    r_m = client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_maha_1"}, headers=headers_maha)
    m_case_id = r_m.json()["id"]
    client.post(f"/api/enforcement/cases/{m_case_id}/calculate-penalty", json={}, headers=headers_maha)
    client.post(f"/api/enforcement/cases/{m_case_id}/notices", json={}, headers=headers_maha)

    # Check Delhi Dashboard
    r_dash_delhi = client.get("/api/enforcement/dashboard", headers=headers_delhi)
    assert r_dash_delhi.status_code == 200
    metrics_d = r_dash_delhi.json()
    assert metrics_d["total_active_cases"] == 1
    assert metrics_d["total_notices_served"] == 1

    # Check Maharashtra Dashboard
    r_dash_maha = client.get("/api/enforcement/dashboard", headers=headers_maha)
    assert r_dash_maha.status_code == 200
    metrics_m = r_dash_maha.json()
    assert metrics_m["total_active_cases"] == 1
    assert metrics_m["total_notices_served"] == 1

    # Check Admin Dashboard (Global statutory oversight)
    headers_admin = make_headers("jur_admin", ROLE_ADMIN)
    r_dash_admin = client.get("/api/enforcement/dashboard", headers=headers_admin)
    assert r_dash_admin.status_code == 200
    metrics_admin = r_dash_admin.json()
    assert metrics_admin["total_active_cases"] == 2
    assert metrics_admin["total_notices_served"] == 2


@pytest.mark.asyncio
async def test_07_district_filtering_within_state_authority():
    """Filtering by district within the same state authority correctly segregates district dockets."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Delhi Central case
    client.post(
        "/api/enforcement/cases",
        json={"analysis_id": "ana_jur_delhi_1", "jurisdiction_district": "Central"},
        headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    )
    # Delhi South case
    client.post(
        "/api/enforcement/cases",
        json={"analysis_id": "ana_jur_delhi_2", "jurisdiction_district": "South"},
        headers=make_headers("jur_delhi_officer_2", ROLE_ENFORCEMENT)
    )

    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_central = client.get("/api/enforcement/cases?jurisdiction_district=Central", headers=headers_delhi)
    assert r_central.status_code == 200
    assert r_central.json()["total"] == 1
    assert r_central.json()["cases"][0]["jurisdiction_district"] == "Central"

    r_south = client.get("/api/enforcement/cases?jurisdiction_district=South", headers=headers_delhi)
    assert r_south.status_code == 200
    assert r_south.json()["total"] == 1
    assert r_south.json()["cases"][0]["jurisdiction_district"] == "South"


@pytest.mark.asyncio
async def test_08_multiple_officers_same_org_collaboration():
    """Officers within the same regulatory authority can view each other's cases."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Officer 1 creates case
    r_create = client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    case_id = r_create.json()["id"]

    # Officer 2 in same authority views and is assigned case
    headers_off2 = make_headers("jur_delhi_officer_2", ROLE_ENFORCEMENT)
    assert client.get(f"/api/enforcement/cases/{case_id}", headers=headers_off2).status_code == 200
    r_assign = client.post(f"/api/enforcement/cases/{case_id}/assign", json={"assigned_officer": "jur_delhi_officer_2"}, headers=headers_off2)
    assert r_assign.status_code == 200
    assert r_assign.json()["assigned_officer"] == "jur_delhi_officer_2"


@pytest.mark.asyncio
async def test_09_state_authority_search_isolation():
    """Product name search is scoped to the caller's authority and does not match foreign authority products."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    # Create Delhi Spices case
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    # Create Mumbai Wafer case
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_maha_1"}, headers=make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT))

    # Delhi officer searches for "Wafer" (in Mumbai only) -> 0 results
    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_search = client.get("/api/enforcement/cases?search=Wafer", headers=headers_delhi)
    assert r_search.status_code == 200
    assert r_search.json()["total"] == 0

    # Delhi officer searches for "Spices" (in Delhi) -> 1 result
    r_spices = client.get("/api/enforcement/cases?search=Spices", headers=headers_delhi)
    assert r_spices.status_code == 200
    assert r_spices.json()["total"] == 1


@pytest.mark.asyncio
async def test_10_severity_filter_scoped_to_jurisdiction():
    """Severity filter returns only cases within caller's regulatory authority."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1", "severity": "CRITICAL"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_maha_1", "severity": "CRITICAL"}, headers=make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT))

    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_crit = client.get("/api/enforcement/cases?severity=CRITICAL", headers=headers_delhi)
    assert r_crit.status_code == 200
    assert r_crit.json()["total"] == 1


@pytest.mark.asyncio
async def test_11_status_filter_scoped_to_jurisdiction():
    """Status filter returns only cases within caller's regulatory authority."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))
    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_maha_1"}, headers=make_headers("jur_maha_officer_1", ROLE_ENFORCEMENT))

    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_open = client.get("/api/enforcement/cases?status=OPEN", headers=headers_delhi)
    assert r_open.status_code == 200
    assert r_open.json()["total"] == 1


@pytest.mark.asyncio
async def test_12_nonexistent_district_filter_returns_empty():
    """Filtering by a district that has no cases returns an empty list without error."""
    await _seed_jurisdiction_data()
    client = TestClient(app)

    client.post("/api/enforcement/cases", json={"analysis_id": "ana_jur_delhi_1"}, headers=make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT))

    headers_delhi = make_headers("jur_delhi_officer_1", ROLE_ENFORCEMENT)
    r_none = client.get("/api/enforcement/cases?jurisdiction_district=UnknownDistrictXYZ", headers=headers_delhi)
    assert r_none.status_code == 200
    assert r_none.json()["total"] == 0
    assert len(r_none.json()["cases"]) == 0

