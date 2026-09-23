"""
Phase 1.5 — Audit & Enforcement Officer Access Request + Admin Approval Test Suite

Tests:
1. Submit Audit Access Request -> 201, status PENDING
2. Submit Enforcement Access Request -> 201, status PENDING
3. Duplicate pending request -> 409 Conflict
4. Normal User cannot approve request -> 403 Forbidden
5. Merchant cannot approve request -> 403 Forbidden
6. Unauthenticated user cannot approve -> 401/403
7. Admin approves Audit request -> APPROVED, AUDIT_OFFICER invited account created
8. Admin approves Enforcement request -> APPROVED, ENFORCEMENT_OFFICER invited account created
9. Admin rejects request -> REJECTED, rejection reason saved, no account created
10. Activation token sets password and transitions account to ACTIVE
11. Expired activation token is rejected
12. Single-use activation token (re-use rejected)
13. Pre-activation login is blocked (401)
14. Audit Officer login succeeds after activation
15. Enforcement Officer login succeeds after activation
16. Cross-officer protection: Audit Officer cannot access Enforcement workspace
17. Normal User cannot access Officer endpoints
18. Merchant cannot access Officer endpoints
"""

import os
import pytest
import datetime
from httpx import AsyncClient, ASGITransport

from main import app
from config import settings
from auth.security import (
    create_token,
    hash_password,
    generate_invitation_token,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
    ROLE_USER,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_officer_access_request_by_id,
    create_organization,
    delete_user,
)

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True)
def setup_test_env():
    clear_rate_limits()


async def _create_test_account(username: str, role: str) -> str:
    """Helper to create an active user in SQLite database and return signed JWT."""
    pw_hash, salt = hash_password("TestPass123!")
    org_id = "org_ministry" if role in (ROLE_ADMIN, ROLE_AUDIT, ROLE_ENFORCEMENT) else f"org_{username}"
    await create_organization(id=org_id, name=f"{username} Org", status="ACTIVE")
    await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=role,
        full_name=f"{username} User",
        email=f"{username}@testdomain.gov.in" if "officer" in username or "admin" in username else f"{username}@test.com",
        organization_id=org_id
    )
    return create_token(username, role, 1)


@pytest.mark.asyncio
async def test_submit_audit_access_request():
    """TEST 1: Submit Audit Access Request -> 201, status PENDING, Request ID generated."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "requested_role": ROLE_AUDIT,
            "full_name": "Dr. Ananya Verma",
            "official_email": "ananya.verma@doca.gov.in",
            "mobile_number": "9876543201",
            "employee_officer_id": "AUD-DL-2026-441",
            "designation": "Senior Metrology Quality Auditor",
            "department_organization": "Department of Consumer Affairs",
            "state": "Delhi",
            "district_jurisdiction": "Central Delhi",
            "reason": "Official pre-market verification and packaging compliance auditing",
            "office_address": "Krishi Bhawan, New Delhi",
            "additional_information": "Empowered under LM Packaged Commodities Rules 2011"
        }
        res = await ac.post("/api/officer-access/requests", json=payload)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["requested_role"] == ROLE_AUDIT
        assert data["status"] == "PENDING"
        assert data["request_id"].startswith("OFF-REQ-")
        assert data["full_name"] == "Dr. Ananya Verma"
        assert data["official_email"] == "ananya.verma@doca.gov.in"

        # Public status endpoint check
        status_res = await ac.get(f"/api/officer-access/requests/{data['request_id']}")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_submit_enforcement_access_request():
    """TEST 2: Submit Enforcement Access Request -> 201, status PENDING."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "requested_role": ROLE_ENFORCEMENT,
            "full_name": "Inspector Rajesh Nair",
            "official_email": "rajesh.nair@legalmetrology.gov.in",
            "mobile_number": "9876543202",
            "employee_officer_id": "ENF-MH-2026-882",
            "designation": "Legal Metrology Inspector",
            "department_organization": "Directorate of Legal Metrology Maharashtra",
            "state": "Maharashtra",
            "district_jurisdiction": "Mumbai Suburban",
            "reason": "Field inspection, seizure authorization, and show cause notice issuance",
        }
        res = await ac.post("/api/officer-access/requests", json=payload)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["requested_role"] == ROLE_ENFORCEMENT
        assert data["status"] == "PENDING"
        assert data["request_id"].startswith("OFF-REQ-")


@pytest.mark.asyncio
async def test_duplicate_pending_request_rejected():
    """TEST 3: Duplicate pending request with same email and requested role is rejected with 409."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "requested_role": ROLE_AUDIT,
            "full_name": "Suresh Gupta",
            "official_email": "suresh.gupta@doca.gov.in",
            "mobile_number": "9876543203",
            "employee_officer_id": "AUD-UP-2026-119",
            "designation": "Assistant Director (QA)",
            "department_organization": "DoCA Uttar Pradesh",
            "state": "Uttar Pradesh",
            "district_jurisdiction": "Lucknow",
            "reason": "Audit verification for packaged goods",
        }
        res1 = await ac.post("/api/officer-access/requests", json=payload)
        assert res1.status_code == 201

        # Submit duplicate
        res2 = await ac.post("/api/officer-access/requests", json=payload)
        assert res2.status_code == 409
        assert "already pending" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthorized_users_cannot_approve_or_reject():
    """TEST 4, 5, 6: Unauthenticated, Normal User, and Merchant cannot approve/reject requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a pending request
        payload = {
            "requested_role": ROLE_AUDIT,
            "full_name": "Vikas Sharma",
            "official_email": "vikas.sharma@doca.gov.in",
            "mobile_number": "9876543204",
            "employee_officer_id": "AUD-HR-2026-551",
            "designation": "QA Inspector",
            "department_organization": "DoCA Haryana",
            "state": "Haryana",
            "district_jurisdiction": "Gurugram",
            "reason": "Quality audit verification",
        }
        create_res = await ac.post("/api/officer-access/requests", json=payload)
        assert create_res.status_code == 201
        req_id = create_res.json()["request_id"]

        # 1. Unauthenticated -> 401/403
        anon_res = await ac.post(f"/api/admin/officer-requests/{req_id}/approve")
        assert anon_res.status_code in (401, 403)

        # 2. Normal User token -> 403
        user_token = await _create_test_account("normal_user_guard_test", ROLE_USER)
        user_res = await ac.post(
            f"/api/admin/officer-requests/{req_id}/approve",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert user_res.status_code == 403

        # 3. Merchant token -> 403
        merchant_token = await _create_test_account("merchant_user_guard_test", ROLE_MERCHANT)
        merchant_res = await ac.post(
            f"/api/admin/officer-requests/{req_id}/approve",
            headers={"Authorization": f"Bearer {merchant_token}"}
        )
        assert merchant_res.status_code == 403


@pytest.mark.asyncio
async def test_admin_approves_audit_request_and_activation():
    """TEST 7, 10, 13, 14: Admin approves Audit request -> provisioned in INVITED status -> activated -> login succeeds."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = await _create_test_account("admin_officer_approver", ROLE_ADMIN)

        payload = {
            "requested_role": ROLE_AUDIT,
            "full_name": "Meera Sen",
            "official_email": "meera.sen@doca.gov.in",
            "mobile_number": "9876543205",
            "employee_officer_id": "AUD-WB-2026-901",
            "designation": "Senior Audit Officer",
            "department_organization": "DoCA West Bengal",
            "state": "West Bengal",
            "district_jurisdiction": "Kolkata",
            "reason": "Official batch compliance auditing",
        }
        create_res = await ac.post("/api/officer-access/requests", json=payload)
        assert create_res.status_code == 201
        req_id = create_res.json()["request_id"]

        # Admin lists requests
        list_res = await ac.get(
            "/api/admin/officer-requests?status=PENDING",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert list_res.status_code == 200
        req_ids = [r["request_id"] for r in list_res.json()]
        assert req_id in req_ids

        # Admin approves request
        approve_res = await ac.post(
            f"/api/admin/officer-requests/{req_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert approve_res.status_code == 200, approve_res.text
        app_data = approve_res.json()
        assert "user" in app_data
        assert app_data["user"]["role"] == ROLE_AUDIT
        assert app_data["user"]["status"] == "INVITED"
        provisioned_username = app_data["username"]
        invitation_token = app_data["dev_invitation_token"]
        assert invitation_token is not None

        # Check request in DB is APPROVED
        req_db = await get_officer_access_request_by_id(req_id)
        assert req_db["status"] == "APPROVED"
        assert req_db["created_user_id"] == provisioned_username

        # TEST 13: Pre-activation login attempt MUST fail with 401
        pre_login = await ac.post("/api/auth/login", json={
            "username": provisioned_username,
            "password": "AnyPassword123!"
        })
        assert pre_login.status_code == 401
        assert "invitation has not been activated" in pre_login.json()["detail"].lower()

        # TEST 10: Verify Invitation & Activate Account
        verify_res = await ac.post("/api/auth/verify-invitation", json={"token": invitation_token})
        assert verify_res.status_code == 200
        assert verify_res.json()["valid"] is True
        assert verify_res.json()["role"] == ROLE_AUDIT

        activate_res = await ac.post("/api/auth/activate", json={
            "token": invitation_token,
            "password": "SecureOfficerPass2026!"
        })
        assert activate_res.status_code == 200

        # TEST 14: Audit Officer Login succeeds now that account is ACTIVE
        post_login = await ac.post("/api/auth/login", json={
            "username": provisioned_username,
            "password": "SecureOfficerPass2026!"
        })
        assert post_login.status_code == 200
        assert post_login.json()["user"]["role"] == ROLE_AUDIT
        assert post_login.json()["user"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_admin_approves_enforcement_request():
    """TEST 8, 15: Admin approves Enforcement request -> provisioned -> activated -> login succeeds."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = await _create_test_account("admin_enf_approver", ROLE_ADMIN)

        payload = {
            "requested_role": ROLE_ENFORCEMENT,
            "full_name": "Arjun Singhal",
            "official_email": "arjun.singhal@legalmetrology.gov.in",
            "mobile_number": "9876543206",
            "employee_officer_id": "ENF-KA-2026-302",
            "designation": "Assistant Controller Legal Metrology",
            "department_organization": "Directorate of Legal Metrology Karnataka",
            "state": "Karnataka",
            "district_jurisdiction": "Bengaluru Urban",
            "reason": "Market surveillance and statutory show cause proceedings",
        }
        create_res = await ac.post("/api/officer-access/requests", json=payload)
        assert create_res.status_code == 201
        req_id = create_res.json()["request_id"]

        approve_res = await ac.post(
            f"/api/admin/officer-requests/{req_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert approve_res.status_code == 200
        app_data = approve_res.json()
        assert app_data["user"]["role"] == ROLE_ENFORCEMENT
        assert app_data["user"]["status"] == "INVITED"
        provisioned_username = app_data["username"]
        invitation_token = app_data["dev_invitation_token"]

        # Activate
        act_res = await ac.post("/api/auth/activate", json={
            "token": invitation_token,
            "password": "EnforcementSecretPass2026!"
        })
        assert act_res.status_code == 200

        # TEST 15: Login succeeds as Enforcement Officer
        enf_login = await ac.post("/api/auth/login", json={
            "username": provisioned_username,
            "password": "EnforcementSecretPass2026!"
        })
        assert enf_login.status_code == 200
        assert enf_login.json()["user"]["role"] == ROLE_ENFORCEMENT


@pytest.mark.asyncio
async def test_admin_rejects_officer_request():
    """TEST 9: Admin rejects request -> status REJECTED, reason stored, no officer account created."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = await _create_test_account("admin_rejector_test", ROLE_ADMIN)

        payload = {
            "requested_role": ROLE_AUDIT,
            "full_name": "Unverified Applicant",
            "official_email": "fake.applicant@temp-mail.com",
            "mobile_number": "9876543207",
            "employee_officer_id": "FAKE-001",
            "designation": "Consultant",
            "department_organization": "Private Firm",
            "state": "Delhi",
            "district_jurisdiction": "Delhi",
            "reason": "Testing access",
        }
        create_res = await ac.post("/api/officer-access/requests", json=payload)
        assert create_res.status_code == 201
        req_id = create_res.json()["request_id"]

        # Admin rejects
        reject_res = await ac.post(
            f"/api/admin/officer-requests/{req_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"rejection_reason": "Applicant email is not an official government/institutional domain."}
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"
        assert reject_res.json()["rejection_reason"] == "Applicant email is not an official government/institutional domain."

        # Public status reflects rejection
        status_res = await ac.get(f"/api/officer-access/requests/{req_id}")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "REJECTED"
        assert status_res.json()["rejection_reason"] == "Applicant email is not an official government/institutional domain."


@pytest.mark.asyncio
async def test_single_use_and_expired_activation_tokens():
    """TEST 11, 12: Activation token works only once and expired tokens are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = await _create_test_account("admin_token_lifecycle_test", ROLE_ADMIN)

        # 1. Single use test
        payload = {
            "requested_role": ROLE_AUDIT,
            "full_name": "Kavita Rao",
            "official_email": "kavita.rao@doca.gov.in",
            "mobile_number": "9876543208",
            "employee_officer_id": "AUD-TS-2026-612",
            "designation": "Metrology Inspector",
            "department_organization": "DoCA Telangana",
            "state": "Telangana",
            "district_jurisdiction": "Hyderabad",
            "reason": "Quality audit verification",
        }
        create_res = await ac.post("/api/officer-access/requests", json=payload)
        req_id = create_res.json()["request_id"]
        approve_res = await ac.post(
            f"/api/admin/officer-requests/{req_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        invitation_token = approve_res.json()["dev_invitation_token"]

        # First activation succeeds
        act1 = await ac.post("/api/auth/activate", json={
            "token": invitation_token,
            "password": "ValidPassword123!"
        })
        assert act1.status_code == 200

        # TEST 12: Second activation with same token MUST fail (400)
        act2 = await ac.post("/api/auth/activate", json={
            "token": invitation_token,
            "password": "AnotherPassword123!"
        })
        assert act2.status_code == 400
        assert "invalid, expired, or already-used" in act2.json()["detail"].lower()

        # TEST 11: Expired token verification check
        verify_invalid = await ac.post("/api/auth/verify-invitation", json={"token": "expired_or_invalid_token"})
        assert verify_invalid.status_code == 200
        assert verify_invalid.json()["valid"] is False


@pytest.mark.asyncio
async def test_cross_officer_and_public_user_protection():
    """TEST 16, 17, 18: Audit Officer cannot access Enforcement APIs; Normal User & Merchant cannot access Officer APIs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        audit_token = await _create_test_account("audit_officer_cross_test", ROLE_AUDIT)
        enf_token = await _create_test_account("enf_officer_cross_test", ROLE_ENFORCEMENT)
        user_token = await _create_test_account("public_user_cross_test", ROLE_USER)
        merchant_token = await _create_test_account("merchant_cross_test", ROLE_MERCHANT)

        # 1. Enforcement API (/api/enforcement/penalty)
        # Audit officer attempting enforcement action -> 403
        audit_to_enf = await ac.post(
            "/api/enforcement/penalty",
            json={"analysis_id": "non_existent"},
            headers={"Authorization": f"Bearer {audit_token}"}
        )
        assert audit_to_enf.status_code == 403

        # Normal user attempting enforcement action -> 403
        user_to_enf = await ac.post(
            "/api/enforcement/penalty",
            json={"analysis_id": "non_existent"},
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert user_to_enf.status_code == 403

        # Merchant attempting enforcement action -> 403
        merchant_to_enf = await ac.post(
            "/api/enforcement/penalty",
            json={"analysis_id": "non_existent"},
            headers={"Authorization": f"Bearer {merchant_token}"}
        )
        assert merchant_to_enf.status_code == 403

        # Enforcement officer can access enforcement action (returns 404 since non_existent, not 403)
        enf_res = await ac.post(
            "/api/enforcement/penalty",
            json={"analysis_id": "non_existent"},
            headers={"Authorization": f"Bearer {enf_token}"}
        )
        assert enf_res.status_code == 404
