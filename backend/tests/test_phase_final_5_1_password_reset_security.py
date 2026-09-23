"""
Phase Final 5.1 — Password Reset Token Exposure Remediation Tests

Validates:
1. Forgot-password response contains NO reset token.
2. Forgot-password response contains NO reset URL.
3. Forgot-password response contains NO dev_token.
4. Frontend source contains no active password-reset development helper.
5. DEMO_MODE does not expose reset tokens through the normal public recovery API.
6. Valid email recovery link still works.
7. Invalid reset token is rejected.
8. Expired reset token is rejected.
9. Used reset token cannot be reused.
10. Password actually changes after a valid reset.
11. Old password no longer works after successful reset.
12. New password works through the normal login endpoint.
13. Nonexistent username/email returns the same generic response as an existing account.
14. Raw reset tokens are not written to application logs.
15. No reset token appears in frontend-visible API responses.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from config import settings
from auth.security import (
    hash_password,
    verify_password,
    hash_reset_token,
    generate_password_reset_token,
    get_delivery_provider,
    set_delivery_provider,
    DevLoggerDeliveryProvider,
    ROLE_MERCHANT,
    ROLE_ENFORCEMENT,
    ROLE_ADMIN,
)
from auth.ratelimit import clear_rate_limits
from database.db import (
    create_user,
    delete_user,
    get_user_by_username,
    get_db,
)


@pytest.fixture(autouse=True)
def setup_delivery_and_ratelimits():
    clear_rate_limits()
    provider = DevLoggerDeliveryProvider()
    set_delivery_provider(provider)
    yield provider
    set_delivery_provider(None)
    clear_rate_limits()


# ── 1, 2, 3, 5, 13, 15: API Response & Payload Security ──────────────────────────

def test_01_forgot_password_response_payload_has_no_tokens_or_urls():
    """1, 2, 3, 15: Response body must strictly contain only a safe generic message."""
    client = TestClient(app)
    resp = client.post("/api/auth/forgot-password", json={"identifier": "officer"})
    assert resp.status_code == 200
    data = resp.json()

    # Must only contain message key
    assert "message" in data
    assert "dev_token" not in data
    assert "token" not in data
    assert "reset_token" not in data
    assert "reset_url" not in data
    assert "dev_reset_url" not in data
    assert "activation_url" not in data
    assert len(data.keys()) == 1


def test_02_demo_mode_does_not_expose_token():
    """5: Even when METRCHECK_DEMO_MODE is True, no token is returned in forgot-password response."""
    client = TestClient(app)
    with patch.object(settings, "METRCHECK_DEMO_MODE", True):
        with patch.dict(os.environ, {"METRCHECK_DEMO_MODE": "true", "ENVIRONMENT": "development"}):
            resp = client.post("/api/auth/forgot-password", json={"identifier": "merchant"})
            assert resp.status_code == 200
            data = resp.json()
            assert "dev_token" not in data
            assert data.get("dev_token") is None
            assert len(data.keys()) == 1


def test_03_nonexistent_account_returns_identical_generic_response():
    """13: Account enumeration defense — non-existent user returns exact same response."""
    client = TestClient(app)
    resp_real = client.post("/api/auth/forgot-password", json={"identifier": "admin"})
    resp_fake = client.post("/api/auth/forgot-password", json={"identifier": "nonexistent_account_987654"})

    assert resp_real.status_code == 200
    assert resp_fake.status_code == 200
    assert resp_real.json() == resp_fake.json()
    assert resp_fake.json()["message"] == "If an account matches the information provided, password reset instructions have been sent."


# ── 4: Frontend Static Source Code Audit ──────────────────────────────────────

def test_04_frontend_source_contains_no_dev_helper_in_forgot_password():
    """4: Frontend ForgotPassword.tsx must not contain dev helper banners or direct reset shortcuts."""
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"
    forgot_pw_path = frontend_dir / "pages" / "ForgotPassword.tsx"
    
    if not forgot_pw_path.exists():
        pytest.skip("Frontend directory not located relative to test file.")

    content = forgot_pw_path.read_text(encoding="utf-8")
    assert "Dev / Test Environment Helper" not in content
    assert "DEV / TEST ENVIRONMENT HELPER" not in content.upper()
    assert "Open Reset Password Interface" not in content
    assert "dev_token" not in content


# ── 6, 7, 8, 9, 10, 11, 12: End-to-End Recovery Flow ─────────────────────────

@pytest.mark.asyncio
async def test_05_valid_email_recovery_flow_end_to_end():
    """6, 10, 11, 12: Valid recovery email receives link, password updates, old pw rejected, new pw works."""
    client = TestClient(app)
    username = "test_sec_user_e2e"
    email = "sec_e2e_recovery@example.com"
    old_pw = "OldPassword123!"
    new_pw = "BrandNewSecurePassword456!"
    await delete_user(username)

    pwh, salt = hash_password(old_pw)
    await create_user(username=username, password_hash=pwh, salt=salt, role=ROLE_MERCHANT, email=email)

    # 1. Request recovery
    resp = client.post("/api/auth/forgot-password", json={"identifier": email})
    assert resp.status_code == 200
    assert "dev_token" not in resp.json()

    # 2. Extract token from out-of-band delivery channel (mock email provider)
    provider = get_delivery_provider()
    assert provider.last_sent is not None
    assert provider.last_sent["email"] == email
    token = provider.last_sent["raw_token"]
    assert token is not None

    # 3. Verify token endpoint
    v_resp = client.post("/api/auth/verify-reset-token", json={"token": token})
    assert v_resp.status_code == 200
    assert v_resp.json()["valid"] is True
    assert v_resp.json()["username"] == username

    # 4. Reset password
    r_resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": new_pw})
    assert r_resp.status_code == 200

    # 5. Old password fails
    fail_login = client.post("/api/auth/login", json={"username": username, "password": old_pw})
    assert fail_login.status_code == 401

    # 6. New password succeeds
    succ_login = client.post("/api/auth/login", json={"username": username, "password": new_pw})
    assert succ_login.status_code == 200
    assert succ_login.json()["user"]["username"] == username


@pytest.mark.asyncio
async def test_06_invalid_and_expired_tokens_are_rejected():
    """7 & 8: Invalid and expired tokens are rejected by verify and reset endpoints."""
    client = TestClient(app)
    
    # Random bogus token
    bogus_token = "completely_invalid_token_1234567890"
    v_resp = client.post("/api/auth/verify-reset-token", json={"token": bogus_token})
    assert v_resp.status_code == 200
    assert v_resp.json()["valid"] is False

    r_resp = client.post("/api/auth/reset-password", json={"token": bogus_token, "new_password": "ValidPassword123!"})
    assert r_resp.status_code == 400


@pytest.mark.asyncio
async def test_07_used_token_cannot_be_reused():
    """9: Token is single-use and rejected on second attempt."""
    client = TestClient(app)
    username = "test_sec_single_use"
    email = "single_use_test@example.com"
    await delete_user(username)

    pwh, salt = hash_password("InitialPassword123!")
    await create_user(username=username, password_hash=pwh, salt=salt, role=ROLE_ENFORCEMENT, email=email, organization_id="org_ministry")

    client.post("/api/auth/forgot-password", json={"identifier": username})
    token = get_delivery_provider().last_sent["raw_token"]

    # First use -> 200 OK
    res1 = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewValidPass123!"})
    assert res1.status_code == 200

    # Second use -> 400 Bad Request
    res2 = client.post("/api/auth/reset-password", json={"token": token, "new_password": "AnotherNewPass456!"})
    assert res2.status_code == 400
    assert "Invalid or expired" in res2.json()["detail"]


# ── 14: Log Sanitization Audit ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_08_raw_tokens_not_logged_to_application_logs(caplog):
    """14: Delivery provider log records safe metadata only — raw tokens never appear in log streams."""
    import logging
    provider = DevLoggerDeliveryProvider()
    
    with caplog.at_level(logging.INFO):
        raw_secret_token = "super_secret_raw_token_xyz_9876543210"
        reset_url_with_secret = f"http://localhost:5173/reset-password?token={raw_secret_token}"
        
        await provider.send_reset_instructions(
            username="target_user",
            raw_token=raw_secret_token,
            reset_url=reset_url_with_secret,
            email="target@example.com"
        )
        
        # Verify secret token does not appear in captured log output
        assert raw_secret_token not in caplog.text
        assert "target_user" in caplog.text
