"""
Unit and Integration Tests for SEC-AUD-12 — Multi-Worker Distributed & Shared Rate Limiting.

Vulnerability Reference: SEC-AUD-12
Components Under Test:
  - backend/auth/ratelimit.py:
      * BaseRateLimiter, SqliteRateLimiter, RedisRateLimiter, InMemoryRateLimiter
      * get_rate_limiter, check_analysis_rate_limit, check_ocr_rate_limit, check_register_rate_limit
      * check_login_rate_limit, record_login_failure, record_login_success
      * check_forgot_password_rate_limit, record_forgot_password_attempt
      * clear_rate_limits
  - backend/config.py:
      * Settings.RATE_LIMIT_BACKEND, Settings.RATE_LIMIT_FAIL_CLOSED
  - backend/database/db.py:
      * rate_limit_events table & indexes
  - API Endpoints:
      * POST /api/analyze, POST /api/ocr, POST /api/auth/register, POST /api/auth/login, POST /api/auth/forgot-password

Security Requirements:
1. Current rate-limit behavior still works as expected.
2. Analysis rate limit enforced (ANALYSIS_IP_MAX).
3. OCR rate limit enforced (OCR_IP_MAX).
4. Registration rate limit enforced (REGISTER_IP_MAX).
5. Different IPs have independent counters.
6. Window expiration works correctly.
7. Concurrent requests across threads/workers share the exact same limits and cannot exceed them.
8. Multiple separate limiter instances share state via the shared persistent SQLite backend.
9. State survives across newly-instantiated limiter instances.
10. Trusted proxy and IP extraction behavior (SEC-AUD-03) remains intact.
11. Spoofed forwarding headers cannot bypass the limiter.
12. Backend storage failure behavior fails closed safely without leaking internal database exceptions.
13. Existing HTTP response/status behavior remains correct (HTTP 429 Too Many Requests).
14. Process-local dictionaries are not authoritative; SQLite records are the source of truth.
15. Rate limiter reset and clear operations work properly across all instances.
"""

import os
import io
import time
import pytest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from PIL import Image

from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from main import app
from database.db import init_db
from auth.ratelimit import (
    SqliteRateLimiter,
    InMemoryRateLimiter,
    RedisRateLimiter,
    get_rate_limiter,
    get_client_ip,
    clear_rate_limits,
    check_analysis_rate_limit,
    check_ocr_rate_limit,
    check_register_rate_limit,
    check_login_rate_limit,
    record_login_failure,
    record_login_success,
    check_forgot_password_rate_limit,
    record_forgot_password_attempt,
    ANALYSIS_IP_MAX,
    OCR_IP_MAX,
    REGISTER_IP_MAX,
    LOGIN_IP_MAX,
    LOGIN_USER_MAX,
    RESET_IP_MAX,
    RESET_ID_MAX,
)


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


def _create_dummy_image_bytes() -> bytes:
    img = Image.new("RGB", (50, 50), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def setup_env():
    _ensure_test_isolation()
    clear_rate_limits()
    yield
    clear_rate_limits()


# ═════════════════════════════════════════════════════════════════════════════
# 1. CORE SHARED PERSISTENCE & MULTI-INSTANCE STATE SHARING
# ═════════════════════════════════════════════════════════════════════════════

def test_01_multiple_limiter_instances_share_state():
    """Two separately instantiated SqliteRateLimiter objects share state via the shared SQLite database."""
    limiter_worker_1 = SqliteRateLimiter(settings.DATABASE_PATH)
    limiter_worker_2 = SqliteRateLimiter(settings.DATABASE_PATH)

    test_key = "test_shared_key_1"
    max_attempts = 5
    window_sec = 60

    # Worker 1 records 3 attempts
    for _ in range(3):
        assert limiter_worker_1.check_and_record(test_key, max_attempts, window_sec) is True

    # Worker 2 immediately sees the 3 attempts and can only record 2 more
    assert limiter_worker_2.check_and_record(test_key, max_attempts, window_sec) is True
    assert limiter_worker_2.check_and_record(test_key, max_attempts, window_sec) is True

    # 6th attempt on Worker 1 is rejected
    assert limiter_worker_1.check_and_record(test_key, max_attempts, window_sec) is False

    # 6th attempt on Worker 2 is also rejected
    assert limiter_worker_2.check_and_record(test_key, max_attempts, window_sec) is False


def test_02_state_persists_in_sqlite_table():
    """Recorded rate-limit events are directly queryable in the rate_limit_events SQLite table."""
    limiter = SqliteRateLimiter(settings.DATABASE_PATH)
    test_key = "test_db_persistence_key"

    limiter.check_and_record(test_key, max_attempts=10, window_sec=60)
    limiter.check_and_record(test_key, max_attempts=10, window_sec=60)

    # Verify directly in database table
    conn = sqlite3.connect(settings.DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rate_limit_events WHERE key = ?", (test_key,))
        count = cursor.fetchone()[0]
        assert count == 2, f"Expected 2 events in SQLite table, found {count}"
    finally:
        conn.close()


def test_03_state_survives_across_limiter_lifecycle():
    """State survives when a rate limiter instance is destroyed and a new one is created."""
    test_key = "test_lifecycle_key"
    limiter_old = SqliteRateLimiter(settings.DATABASE_PATH)

    for _ in range(4):
        limiter_old.check_and_record(test_key, max_attempts=5, window_sec=60)

    # Destroy reference
    del limiter_old

    # Create new instance (simulating worker restart or another process)
    limiter_new = SqliteRateLimiter(settings.DATABASE_PATH)
    # Only 1 attempt remaining
    assert limiter_new.check_and_record(test_key, max_attempts=5, window_sec=60) is True
    assert limiter_new.check_and_record(test_key, max_attempts=5, window_sec=60) is False


# ═════════════════════════════════════════════════════════════════════════════
# 2. CONCURRENCY & RACE CONDITION SAFETY
# ═════════════════════════════════════════════════════════════════════════════

def test_04_concurrent_requests_cannot_exceed_global_limit():
    """
    High-concurrency test: 30 concurrent threads simulating multiple worker processes
    attempting to record against a limit of 10. Exactly 10 must succeed, and 20 must be rejected.
    """
    test_key = "test_concurrent_key"
    max_attempts = 10
    window_sec = 60
    total_threads = 30

    def _attempt_worker(worker_id: int) -> bool:
        # Each thread uses its own limiter instance
        worker_limiter = SqliteRateLimiter(settings.DATABASE_PATH)
        return worker_limiter.check_and_record(test_key, max_attempts, window_sec)

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(_attempt_worker, range(total_threads)))

    allowed_count = sum(1 for r in results if r is True)
    rejected_count = sum(1 for r in results if r is False)

    assert allowed_count == max_attempts, f"Expected exactly {max_attempts} allowed, got {allowed_count}"
    assert rejected_count == (total_threads - max_attempts), f"Expected {total_threads - max_attempts} rejected, got {rejected_count}"


# ═════════════════════════════════════════════════════════════════════════════
# 3. WINDOW EXPIRATION & RESET BEHAVIOR
# ═════════════════════════════════════════════════════════════════════════════

def test_05_window_expiration_restores_allowance():
    """Past events older than window_sec are pruned and do not block subsequent attempts."""
    limiter = SqliteRateLimiter(settings.DATABASE_PATH)
    test_key = "test_expiration_key"
    window_sec = 2
    max_attempts = 2

    # Exhaust limit
    assert limiter.check_and_record(test_key, max_attempts, window_sec) is True
    assert limiter.check_and_record(test_key, max_attempts, window_sec) is True
    assert limiter.check_and_record(test_key, max_attempts, window_sec) is False

    # Insert events manually with timestamps in the past
    conn = sqlite3.connect(settings.DATABASE_PATH)
    try:
        past_ts = time.time() - 10.0
        conn.execute("UPDATE rate_limit_events SET timestamp = ? WHERE key = ?", (past_ts, test_key))
        conn.commit()
    finally:
        conn.close()

    # Now the limiter should prune old timestamps and allow new requests
    assert limiter.check_and_record(test_key, max_attempts, window_sec) is True


def test_06_reset_key_and_clear_all():
    """reset(key) removes records for that key; clear_all() clears all records."""
    limiter = SqliteRateLimiter(settings.DATABASE_PATH)
    key_a = "key_a"
    key_b = "key_b"

    limiter.check_and_record(key_a, 2, 60)
    limiter.check_and_record(key_b, 2, 60)

    # Reset key_a
    limiter.reset(key_a)
    assert limiter.is_allowed(key_a, 2, 60) is True

    # Clear all
    limiter.clear_all()
    conn = sqlite3.connect(settings.DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rate_limit_events")
        assert cursor.fetchone()[0] == 0
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# 4. IP INDEPENDENCE & ENDPOINT INTEGRATION
# ═════════════════════════════════════════════════════════════════════════════

def test_07_different_ips_have_independent_limits():
    """Limits on IP A do not impact requests from IP B."""
    ip_a = "192.0.2.1"
    ip_b = "192.0.2.2"

    for _ in range(ANALYSIS_IP_MAX):
        allowed, _ = check_analysis_rate_limit(ip_a)
        assert allowed is True

    # IP A is throttled
    allowed_a, msg_a = check_analysis_rate_limit(ip_a)
    assert allowed_a is False
    assert "Rate limit exceeded" in msg_a

    # IP B is still completely allowed
    allowed_b, _ = check_analysis_rate_limit(ip_b)
    assert allowed_b is True


@pytest.mark.asyncio
async def test_08_ocr_rate_limiting_enforced():
    """OCR rate limiter enforces OCR_IP_MAX threshold."""
    await init_db()
    client = TestClient(app)
    img_bytes = _create_dummy_image_bytes()

    for i in range(OCR_IP_MAX):
        resp = client.post("/api/ocr", files={"file": ("ocr.jpg", io.BytesIO(img_bytes), "image/jpeg")})
        assert resp.status_code != 429, f"Request {i+1} was unexpectedly throttled"

    throttled = client.post("/api/ocr", files={"file": ("ocr.jpg", io.BytesIO(img_bytes), "image/jpeg")})
    assert throttled.status_code == 429
    assert "rate limit exceeded" in throttled.json()["detail"].lower()


@pytest.mark.asyncio
async def test_09_registration_rate_limiting_enforced():
    """Registration endpoint enforces REGISTER_IP_MAX threshold."""
    await init_db()
    client = TestClient(app)

    for i in range(REGISTER_IP_MAX):
        u = f"dist_user_{i}_{os.urandom(3).hex()}"
        resp = client.post(
            "/api/auth/register",
            json={
                "username": u,
                "email": f"{u}@merchant.com",
                "password": "SecurePassword123!",
                "full_name": f"Merchant {u}",
                "organization_name": f"Org {u}",
            }
        )
        assert resp.status_code in (200, 201)

    throttled = client.post(
        "/api/auth/register",
        json={
            "username": "dist_blocked_user",
            "email": "dist_blocked@merchant.com",
            "password": "SecurePassword123!",
            "full_name": "Blocked",
            "organization_name": "Blocked Org",
        }
    )
    assert throttled.status_code == 429
    assert "too many registration attempts" in throttled.json()["detail"].lower()


# ═════════════════════════════════════════════════════════════════════════════
# 5. LOGIN & PASSWORD RECOVERY RATE LIMITING
# ═════════════════════════════════════════════════════════════════════════════

def test_10_login_failure_and_success_lifecycle():
    """Failed logins record attempts; successful login resets counters."""
    client_ip = "198.51.100.77"
    username = "test_merchant_sec12"

    for _ in range(LOGIN_USER_MAX):
        allowed, _ = check_login_rate_limit(client_ip, username)
        assert allowed is True
        record_login_failure(client_ip, username)

    # Throttled on next check
    allowed, msg = check_login_rate_limit(client_ip, username)
    assert allowed is False
    assert "Too many failed login attempts" in msg

    # Successful login resets the counter
    record_login_success(client_ip, username)
    allowed_after, _ = check_login_rate_limit(client_ip, username)
    assert allowed_after is True


def test_11_forgot_password_rate_limiting():
    """Password recovery is throttled after RESET_IP_MAX attempts."""
    client_ip = "198.51.100.88"
    identifier = "admin@gov.in"

    for _ in range(RESET_ID_MAX):
        allowed, _ = check_forgot_password_rate_limit(client_ip, identifier)
        assert allowed is True
        record_forgot_password_attempt(client_ip, identifier)

    allowed, msg = check_forgot_password_rate_limit(client_ip, identifier)
    assert allowed is False
    assert "Too many password recovery requests" in msg


# ═════════════════════════════════════════════════════════════════════════════
# 6. FAIL-CLOSED BEHAVIOR & ERROR HANDLING
# ═════════════════════════════════════════════════════════════════════════════

def test_12_backend_failure_fails_closed_safely(monkeypatch):
    """When the underlying SQLite database encounters an error, rate limiting fails closed safely."""
    failing_limiter = SqliteRateLimiter(settings.DATABASE_PATH)

    def _failing_get_conn():
        raise sqlite3.OperationalError("disk I/O error or corruption")

    monkeypatch.setattr(failing_limiter, "_get_connection", _failing_get_conn)

    # 1. When FAIL_CLOSED is True (default), it must return False (deny) and NOT crash
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_CLOSED", True)
    assert failing_limiter.check_and_record("any_key", max_attempts=5, window_sec=60) is False
    assert failing_limiter.is_allowed("any_key", max_attempts=5, window_sec=60) is False

    # 2. When FAIL_CLOSED is False, it returns True (fail open)
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_CLOSED", False)
    assert failing_limiter.check_and_record("any_key", max_attempts=5, window_sec=60) is True
    assert failing_limiter.is_allowed("any_key", max_attempts=5, window_sec=60) is True


def test_13_redis_limiter_falls_back_when_redis_unavailable():
    """RedisRateLimiter safely falls back to SQLite backend when Redis is unreachable."""
    redis_limiter = RedisRateLimiter("redis://127.0.0.1:54321/15")  # unroutable dummy port

    # Operation must gracefully fall back to SQLite limiter and succeed
    test_key = "test_redis_fallback"
    assert redis_limiter.check_and_record(test_key, max_attempts=5, window_sec=60) is True
    assert redis_limiter.is_allowed(test_key, max_attempts=5, window_sec=60) is True


def test_14_factory_respects_settings_configuration():
    """get_rate_limiter() returns the appropriate class according to settings.RATE_LIMIT_BACKEND."""
    limiter = get_rate_limiter()
    assert isinstance(limiter, SqliteRateLimiter)


def test_15_trusted_proxy_and_spoofing_integration():
    """Verify SEC-AUD-03 get_client_ip integration with rate limiting."""
    class FakeRequest:
        def __init__(self, host, x_real_ip=None, x_forwarded_for=None):
            from starlette.datastructures import Address, Headers
            self.client = Address(host, 12345)
            headers = {}
            if x_real_ip:
                headers["x-real-ip"] = x_real_ip
            if x_forwarded_for:
                headers["x-forwarded-for"] = x_forwarded_for
            self.headers = Headers(headers)

    # Untrusted direct client attempting to spoof headers
    untrusted_req = FakeRequest("203.0.113.10", x_real_ip="8.8.8.8", x_forwarded_for="9.9.9.9")
    resolved_ip = get_client_ip(untrusted_req)
    assert resolved_ip == "203.0.113.10"

    # Trusted proxy passing real client IP
    trusted_req = FakeRequest("127.0.0.1", x_real_ip="203.0.113.55")
    resolved_trusted = get_client_ip(trusted_req)
    assert resolved_trusted == "203.0.113.55"
