import pytest
import os
from httpx import AsyncClient, ASGITransport
from main import app
from database.db import get_user_by_username, get_organization
from auth.security import ROLE_USER, ROLE_MERCHANT, ROLE_AUDIT, ROLE_ENFORCEMENT, decode_token

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_normal_user_registration_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Normal User Registration
        payload = {
            "full_name": "Test Consumer",
            "username": "consumer_test_01",
            "email": "consumer01@test.com",
            "password": "Password123!",
            "mobile_number": "9876543210"
        }
        res = await ac.post("/api/auth/register-user", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert "token" in data
        assert data["user"]["username"] == "consumer_test_01"
        assert data["user"]["role"] == ROLE_USER
        assert data["user"]["role_label"] == "Normal User"

        # Verify token
        decoded = decode_token(data["token"])
        assert decoded is not None
        assert decoded["sub"] == "consumer_test_01"
        assert decoded["role"] == ROLE_USER

        # Verify DB organization
        user_in_db = await get_user_by_username("consumer_test_01")
        assert user_in_db is not None
        assert user_in_db["role"] == ROLE_USER
        assert user_in_db["organization_id"] == "org_user_consumer_test_01"

        # 2. Login with Normal User
        login_res = await ac.post("/api/auth/login", json={
            "username": "consumer_test_01",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        assert login_res.json()["user"]["role"] == ROLE_USER


@pytest.mark.asyncio
async def test_merchant_registration_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Merchant Registration with full business fields
        payload = {
            "full_name": "Merchant Owner",
            "username": "merchant_test_01",
            "email": "merchant01@business.com",
            "mobile_number": "9876543211",
            "password": "Password123!",
            "business_name": "Acme FMCG Pvt Ltd",
            "business_type": "Manufacturer",
            "trade_name": "Acme Organics",
            "address_line1": "Plot 42, Sector 18",
            "address_line2": "Industrial Area",
            "city": "Gurugram",
            "state": "Haryana",
            "pincode": "122001",
            "country": "India",
            "gstin": "06AAAAA0000A1Z5",
            "fssai_license": "10022064000001",
            "legal_metrology_license": "LM-HR-2026-99"
        }
        res = await ac.post("/api/auth/register-merchant", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert "token" in data
        assert data["user"]["username"] == "merchant_test_01"
        assert data["user"]["role"] == ROLE_MERCHANT
        assert data["user"]["role_label"] == "Brand / Merchant"

        # Verify DB organization
        user_in_db = await get_user_by_username("merchant_test_01")
        assert user_in_db is not None
        assert user_in_db["role"] == ROLE_MERCHANT
        assert user_in_db["organization_id"] == "org_merchant_test_01"
        org = await get_organization("org_merchant_test_01")
        assert org is not None
        assert org["name"] == "Acme FMCG Pvt Ltd"

        # 2. Login with Merchant
        login_res = await ac.post("/api/auth/login", json={
            "username": "merchant_test_01",
            "password": "Password123!"
        })
        assert login_res.status_code == 200
        assert login_res.json()["user"]["role"] == ROLE_MERCHANT


@pytest.mark.asyncio
async def test_officer_cannot_be_publicly_registered():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Public self registration at /api/auth/register cannot request OFFICER or ADMIN role
        payload = {
            "username": "fake_officer",
            "email": "fake_officer@test.com",
            "password": "Password123!",
            "role": ROLE_ENFORCEMENT
        }
        res = await ac.post("/api/auth/register", json=payload)
        # Should be rejected with 403 Forbidden
        assert res.status_code == 403
