"""
Unit and Integration Tests for SEC-AUD-10 — Production CORS Wildcard Hardening.

Vulnerability Reference: SEC-AUD-10
Components Under Test:
  - backend/config.py: Settings, parse_cors_origins, validate_production_secrets
  - backend/main.py: CORSMiddleware, lifespan startup configuration validation

Security Requirements:
1. Production mode strictly rejects startup if CORS_ORIGINS contains wildcard ('*') when credentials are enabled.
2. Production mode accepts valid explicit single or multiple trusted origins (e.g., https://metrcheck.gov.in).
3. Development mode preserves default/wildcard origins for local development flexibility.
4. Test mode (TEST_MODE=True) allows automated test isolation.
5. Error messages for rejected CORS configurations are deterministic, clear, and never leak cryptographic secrets.
6. Valid production configurations (strong SECRET_KEY + explicit CORS_ORIGINS) pass validation seamlessly.
"""

import os
import pytest
from unittest.mock import patch

from config import Settings, settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import create_token, decode_token, ROLE_ADMIN


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


VALID_PROD_SECRET = "c7e8a912b45f60d3e1f2a3b4c5d6e7f809123456789abcdef0123456789abcde"


# ═════════════════════════════════════════════════════════════════════════════
# 1. PRODUCTION WILDCARD CORS REJECTION
# ═════════════════════════════════════════════════════════════════════════════

def test_01_production_wildcard_cors_rejected():
    """TEST 1: Production mode with wildcard CORS ['*'] must fail configuration validation."""
    _ensure_test_isolation()
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=VALID_PROD_SECRET,
            CORS_ORIGINS=["*"],
            TEST_MODE=False
        )
    assert "Wildcard CORS ('*') is prohibited in production environments" in str(exc_info.value)


def test_02_production_wildcard_mixed_with_domains_rejected():
    """TEST 2: Production mode with wildcard mixed into origins list must be rejected."""
    _ensure_test_isolation()
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=VALID_PROD_SECRET,
            CORS_ORIGINS=["https://metrcheck.gov.in", "*"],
            TEST_MODE=False
        )
    assert "Wildcard CORS ('*') is prohibited in production environments" in str(exc_info.value)


def test_03_production_string_wildcard_cors_rejected():
    """TEST 3: Production mode with string-based wildcard CORS '*' must fail validation."""
    _ensure_test_isolation()
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=VALID_PROD_SECRET,
            CORS_ORIGINS="*",
            TEST_MODE=False
        )
    assert "Wildcard CORS ('*') is prohibited in production environments" in str(exc_info.value)


# ═════════════════════════════════════════════════════════════════════════════
# 2. PRODUCTION EXPLICIT TRUSTED ORIGINS ACCEPTANCE
# ═════════════════════════════════════════════════════════════════════════════

def test_04_production_explicit_single_origin_accepted():
    """TEST 4: Production mode with a single explicit trusted HTTPS origin is accepted."""
    _ensure_test_isolation()
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=VALID_PROD_SECRET,
        CORS_ORIGINS=["https://metrcheck.gov.in"],
        TEST_MODE=False
    )
    assert s.ENVIRONMENT == "production"
    assert s.CORS_ORIGINS == ["https://metrcheck.gov.in"]


def test_05_production_explicit_multiple_origins_accepted():
    """TEST 5: Production mode with multiple explicit trusted origins is accepted."""
    _ensure_test_isolation()
    trusted = ["https://metrcheck.gov.in", "https://app.metrcheck.gov.in", "https://admin.metrcheck.gov.in"]
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=VALID_PROD_SECRET,
        CORS_ORIGINS=trusted,
        TEST_MODE=False
    )
    assert s.CORS_ORIGINS == trusted


def test_06_production_comma_separated_origins_parsed_and_accepted():
    """TEST 6: Production mode with comma-separated string origins parses and passes."""
    _ensure_test_isolation()
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=VALID_PROD_SECRET,
        CORS_ORIGINS="https://metrcheck.gov.in, https://portal.metrcheck.gov.in",
        TEST_MODE=False
    )
    assert s.CORS_ORIGINS == ["https://metrcheck.gov.in", "https://portal.metrcheck.gov.in"]


# ═════════════════════════════════════════════════════════════════════════════
# 3. DEVELOPMENT & TEST PRESERVATION
# ═════════════════════════════════════════════════════════════════════════════

def test_07_development_wildcard_cors_preserved():
    """TEST 7: Development mode allows wildcard CORS for local development and rapid prototyping."""
    _ensure_test_isolation()
    s = Settings(
        ENVIRONMENT="development",
        SECRET_KEY="metrcheck-dev-secret-change-in-prod",
        CORS_ORIGINS=["*"],
        TEST_MODE=False
    )
    assert s.ENVIRONMENT == "development"
    assert s.CORS_ORIGINS == ["*"]


def test_08_test_mode_bypasses_production_cors_enforcement():
    """TEST 8: TEST_MODE=True bypasses production CORS restrictions for isolated unit tests."""
    _ensure_test_isolation()
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="test_key",
        CORS_ORIGINS=["*"],
        TEST_MODE=True
    )
    assert s.TEST_MODE is True
    assert s.CORS_ORIGINS == ["*"]


# ═════════════════════════════════════════════════════════════════════════════
# 4. ERROR DETERMINISM & LEAKAGE PREVENTION
# ═════════════════════════════════════════════════════════════════════════════

def test_09_validation_error_actionable_and_does_not_leak_secrets():
    """TEST 9: Validation error provides actionable remediation instructions and never leaks secret keys."""
    _ensure_test_isolation()
    sensitive_secret = "my_super_secret_production_key_1234567890"
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=sensitive_secret,
            CORS_ORIGINS=["*"],
            TEST_MODE=False
        )
    err_str = str(exc_info.value)
    assert sensitive_secret not in err_str, "Validation error must never echo the SECRET_KEY"
    assert "Configure explicit trusted domain origins in CORS_ORIGINS" in err_str


def test_10_changing_cors_preserves_authentication_and_unrelated_settings():
    """TEST 10: Changing CORS configuration does not disrupt auth token creation, decoding, or unrelated settings."""
    _ensure_test_isolation()
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=VALID_PROD_SECRET,
        CORS_ORIGINS=["https://metrcheck.gov.in"],
        MAX_FILE_SIZE_MB=25,
        TEST_MODE=False
    )
    assert s.MAX_FILE_SIZE_MB == 25
    assert s.CORS_ORIGINS == ["https://metrcheck.gov.in"]

    # Verify token operations continue functioning normally
    with patch("auth.security.settings", s):
        token = create_token("admin_user", ROLE_ADMIN)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "admin_user"
        assert payload["role"] == ROLE_ADMIN
