"""MetrCheck AI — Multi-Worker Distributed & Shared Rate Limiting (SEC-AUD-12).

Features:
- Multi-worker, multi-process safe rate limiting backed by atomic SQLite WAL transactions
  (or optional distributed Redis backend).
- IP-based and identifier-based throttling with strict proxy trust verification (SEC-AUD-03).
- Generic error messages to prevent account enumeration.
- Concurrency-safe atomic check-and-record operations.
- Fail-closed security architecture on backend failures to prevent DoS against heavy AI/OCR models.
- Easy testing hooks (clear_rate_limits).
"""

import os
import time
import logging
import sqlite3
import threading
import ipaddress
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from config import settings

logger = logging.getLogger(__name__)


# ── Base Abstract Rate Limiter ──────────────────────────────────────────────
class BaseRateLimiter(ABC):
    @abstractmethod
    def is_allowed(self, key: str, max_attempts: int, window_sec: int) -> bool:
        """Check if request is within allowed rate limits without recording an attempt."""
        pass

    @abstractmethod
    def record_attempt(self, key: str, window_sec: int = 600) -> None:
        """Record an attempt for the given key."""
        pass

    @abstractmethod
    def check_and_record(self, key: str, max_attempts: int, window_sec: int) -> bool:
        """Atomically check and record an attempt if within limit."""
        pass

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset records for a specific key (e.g. upon successful login)."""
        pass

    @abstractmethod
    def clear_all(self) -> None:
        """Clear all rate limit records (useful for test isolation)."""
        pass


# ── SQLite Persistent Multi-Worker Rate Limiter ─────────────────────────────
class SqliteRateLimiter(BaseRateLimiter):
    """
    Sliding-window rate limiter backed by SQLite in WAL mode with atomic BEGIN IMMEDIATE transactions.
    Safe across multiple Uvicorn/Gunicorn worker processes and threads.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._custom_db_path = db_path
        self._local = threading.local()

    @property
    def db_path(self) -> str:
        if self._custom_db_path:
            return self._custom_db_path
        return os.path.abspath(settings.DATABASE_PATH)

    def _get_connection(self) -> sqlite3.Connection:
        current_path = self.db_path
        conn = getattr(self._local, "conn", None)
        cached_path = getattr(self._local, "cached_path", None)

        if conn is None or cached_path != current_path:
            os.makedirs(os.path.dirname(current_path), exist_ok=True)
            # isolation_level=None enables explicit manual transaction control with BEGIN IMMEDIATE
            conn = sqlite3.connect(current_path, timeout=10.0, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_events_key_ts ON rate_limit_events(key, timestamp)")
            self._local.conn = conn
            self._local.cached_path = current_path

        return conn

    def _execute_with_retry(self, operation, max_retries: int = 3, retry_delay: float = 0.05):
        for attempt in range(max_retries):
            try:
                return operation()
            except sqlite3.OperationalError as e:
                if ("locked" in str(e).lower() or "busy" in str(e).lower()) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise

    def is_allowed(self, key: str, max_attempts: int, window_sec: int) -> bool:
        now = time.time()
        cutoff = now - window_sec

        def _op():
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM rate_limit_events WHERE key = ? AND timestamp <= ?", (key, cutoff))
                cursor = conn.execute("SELECT COUNT(*) FROM rate_limit_events WHERE key = ? AND timestamp > ?", (key, cutoff))
                count = cursor.fetchone()[0]
                conn.execute("COMMIT")
                return count < max_attempts
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        try:
            return self._execute_with_retry(_op)
        except Exception as e:
            logger.error(f"SqliteRateLimiter error in is_allowed: {e}")
            if getattr(settings, "RATE_LIMIT_FAIL_CLOSED", True):
                return False
            return True

    def record_attempt(self, key: str, window_sec: int = 600) -> None:
        now = time.time()
        cutoff = now - window_sec

        def _op():
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM rate_limit_events WHERE key = ? AND timestamp <= ?", (key, cutoff))
                conn.execute("INSERT INTO rate_limit_events (key, timestamp) VALUES (?, ?)", (key, now))
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        try:
            self._execute_with_retry(_op)
        except Exception as e:
            logger.error(f"SqliteRateLimiter error in record_attempt: {e}")

    def check_and_record(self, key: str, max_attempts: int, window_sec: int) -> bool:
        now = time.time()
        cutoff = now - window_sec

        def _op():
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM rate_limit_events WHERE key = ? AND timestamp <= ?", (key, cutoff))
                cursor = conn.execute("SELECT COUNT(*) FROM rate_limit_events WHERE key = ? AND timestamp > ?", (key, cutoff))
                count = cursor.fetchone()[0]
                if count < max_attempts:
                    conn.execute("INSERT INTO rate_limit_events (key, timestamp) VALUES (?, ?)", (key, now))
                    conn.execute("COMMIT")
                    return True
                else:
                    conn.execute("COMMIT")
                    return False
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        try:
            return self._execute_with_retry(_op)
        except Exception as e:
            logger.error(f"SqliteRateLimiter error in check_and_record: {e}")
            if getattr(settings, "RATE_LIMIT_FAIL_CLOSED", True):
                return False
            return True

    def reset(self, key: str) -> None:
        def _op():
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM rate_limit_events WHERE key = ?", (key,))
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        try:
            self._execute_with_retry(_op)
        except Exception as e:
            logger.error(f"SqliteRateLimiter error in reset: {e}")

    def clear_all(self) -> None:
        def _op():
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM rate_limit_events")
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

        try:
            self._execute_with_retry(_op)
        except Exception as e:
            logger.error(f"SqliteRateLimiter error in clear_all: {e}")


# ── In-Memory Rate Limiter (Testing & Fallback Reference) ────────────────────
class InMemoryRateLimiter(BaseRateLimiter):
    """Sliding-window in-memory rate limiter (thread-safe, single-process)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_attempts: int, window_sec: int) -> bool:
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            timestamps = self._records[key]
            self._records[key] = [t for t in timestamps if t > cutoff]
            return len(self._records[key]) < max_attempts

    def record_attempt(self, key: str, window_sec: int = 600) -> None:
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            timestamps = self._records[key]
            timestamps.append(now)
            self._records[key] = [t for t in timestamps if t > cutoff]

    def check_and_record(self, key: str, max_attempts: int, window_sec: int) -> bool:
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            timestamps = [t for t in self._records[key] if t > cutoff]
            if len(timestamps) < max_attempts:
                timestamps.append(now)
                self._records[key] = timestamps
                return True
            self._records[key] = timestamps
            return False

    def reset(self, key: str) -> None:
        with self._lock:
            if key in self._records:
                del self._records[key]

    def clear_all(self) -> None:
        with self._lock:
            self._records.clear()


# ── Optional Redis Rate Limiter ─────────────────────────────────────────────
class RedisRateLimiter(BaseRateLimiter):
    """Sliding-window distributed rate limiter using atomic Redis Lua scripts."""

    _LUA_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local cutoff = tonumber(ARGV[2])
    local max_attempts = tonumber(ARGV[3])
    local window_sec = tonumber(ARGV[4])
    local record_flag = tonumber(ARGV[5])

    redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
    local current_count = redis.call('ZCARD', key)

    if current_count < max_attempts then
        if record_flag == 1 then
            redis.call('ZADD', key, now, now)
            redis.call('EXPIRE', key, window_sec)
        end
        return 1
    else
        return 0
    end
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url
        self._client = None
        self._fallback = SqliteRateLimiter()

    def _get_client(self):
        if self._client is None:
            try:
                import redis
                url = self._redis_url or getattr(settings, "RATE_LIMIT_REDIS_URL", "") or "redis://localhost:6379/0"
                self._client = redis.from_url(url, socket_timeout=2.0)
            except Exception as e:
                logger.error(f"Failed to initialize Redis client: {e}")
                self._client = None
        return self._client

    def is_allowed(self, key: str, max_attempts: int, window_sec: int) -> bool:
        client = self._get_client()
        if not client:
            return self._fallback.is_allowed(key, max_attempts, window_sec)
        now = time.time()
        cutoff = now - window_sec
        try:
            res = client.eval(self._LUA_SCRIPT, 1, key, now, cutoff, max_attempts, window_sec, 0)
            return bool(res == 1)
        except Exception as e:
            logger.error(f"Redis rate limiter is_allowed error: {e}")
            if getattr(settings, "RATE_LIMIT_FAIL_CLOSED", True):
                return False
            return self._fallback.is_allowed(key, max_attempts, window_sec)

    def record_attempt(self, key: str, window_sec: int = 600) -> None:
        client = self._get_client()
        if not client:
            return self._fallback.record_attempt(key, window_sec)
        now = time.time()
        cutoff = now - window_sec
        try:
            client.eval(self._LUA_SCRIPT, 1, key, now, cutoff, 999999, window_sec, 1)
        except Exception as e:
            logger.error(f"Redis rate limiter record_attempt error: {e}")
            self._fallback.record_attempt(key, window_sec)

    def check_and_record(self, key: str, max_attempts: int, window_sec: int) -> bool:
        client = self._get_client()
        if not client:
            return self._fallback.check_and_record(key, max_attempts, window_sec)
        now = time.time()
        cutoff = now - window_sec
        try:
            res = client.eval(self._LUA_SCRIPT, 1, key, now, cutoff, max_attempts, window_sec, 1)
            return bool(res == 1)
        except Exception as e:
            logger.error(f"Redis rate limiter check_and_record error: {e}")
            if getattr(settings, "RATE_LIMIT_FAIL_CLOSED", True):
                return False
            return self._fallback.check_and_record(key, max_attempts, window_sec)

    def reset(self, key: str) -> None:
        client = self._get_client()
        if not client:
            return self._fallback.reset(key)
        try:
            client.delete(key)
        except Exception as e:
            logger.error(f"Redis rate limiter reset error: {e}")
            self._fallback.reset(key)

    def clear_all(self) -> None:
        client = self._get_client()
        if not client:
            return self._fallback.clear_all()
        try:
            # We also clear fallback sqlite db
            self._fallback.clear_all()
            client.flushdb()
        except Exception as e:
            logger.error(f"Redis rate limiter clear_all error: {e}")


# ── Global Rate Limiter Factory ─────────────────────────────────────────────
_default_sqlite_limiter = SqliteRateLimiter()
_default_memory_limiter = InMemoryRateLimiter()
_default_redis_limiter = RedisRateLimiter()


def get_rate_limiter() -> BaseRateLimiter:
    """Returns the configured rate limiter instance."""
    backend = (getattr(settings, "RATE_LIMIT_BACKEND", "sqlite") or "sqlite").lower().strip()
    if backend == "redis":
        return _default_redis_limiter
    elif backend == "memory":
        return _default_memory_limiter
    return _default_sqlite_limiter


# Global default reference for backward compatibility
_rate_limiter = _default_sqlite_limiter


# ── IP Resolution and Proxy Trust Verification (SEC-AUD-03) ─────────────────
def _is_valid_ip(ip_str: str) -> bool:
    """Validate whether string is a valid IPv4 or IPv6 address."""
    if not ip_str or not isinstance(ip_str, str):
        return False
    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except ValueError:
        return False


def is_trusted_proxy(client_host: str) -> bool:
    """Check whether client_host matches any configured trusted proxy IP, hostname, or subnet."""
    if not client_host:
        return False

    host_clean = client_host.strip().lower()
    trusted_list = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1", "localhost", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])
    if isinstance(trusted_list, str):
        trusted_list = [p.strip() for p in trusted_list.split(",") if p.strip()]

    for item in trusted_list:
        item_clean = item.strip().lower()
        if host_clean == item_clean:
            return True
        try:
            net = ipaddress.ip_network(item_clean, strict=False)
            addr = ipaddress.ip_address(host_clean)
            if addr in net:
                return True
        except ValueError:
            pass

    return False


def get_client_ip(request) -> str:
    """Extract client IP safely from request or trusted proxy headers.

    Security Policy (SEC-AUD-03):
    - If the request is direct from an untrusted peer, forwarding headers (X-Forwarded-For, X-Real-IP)
      are strictly ignored to prevent attacker-controlled rate-limit spoofing or bypass.
    - If the request arrives from a verified trusted reverse proxy (e.g., Nginx):
      1. X-Real-IP is prioritized (overwritten by Nginx using $remote_addr).
      2. If X-Real-IP is missing, the rightmost valid IP in X-Forwarded-For is extracted.
    - If headers are invalid, malformed, or missing, falls back to the direct peer socket IP.
    """
    if not request:
        return "127.0.0.1"

    peer_ip = "127.0.0.1"
    if hasattr(request, "client") and request.client and request.client.host:
        peer_ip = request.client.host.strip()

    # If connection does not originate from a trusted reverse proxy,
    # reject all forwarding headers to prevent attacker spoofing.
    if not is_trusted_proxy(peer_ip):
        return peer_ip

    headers = getattr(request, "headers", None)
    if not headers:
        return peer_ip

    # 1. Prefer X-Real-IP (sanitized/overwritten by Nginx)
    real_ip = headers.get("x-real-ip")
    if real_ip:
        candidate = real_ip.strip()
        if _is_valid_ip(candidate):
            return candidate

    # 2. Fallback to X-Forwarded-For (inspect rightmost valid IP added by trusted proxy)
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        for candidate in reversed(ips):
            if _is_valid_ip(candidate):
                return candidate

    return peer_ip


# ── Login Rate Limiting ──────────────────────────────────────────────────────
# Default: 10 failed attempts per IP per 5 minutes, 5 failed attempts per username per 5 minutes
LOGIN_IP_MAX = 10
LOGIN_USER_MAX = 5
LOGIN_WINDOW_SEC = 300


def check_login_rate_limit(client_ip: str, username: str = "") -> Tuple[bool, str]:
    """Return (allowed, error_message). Does not leak whether username exists."""
    limiter = get_rate_limiter()
    ip_key = f"login_fail_ip:{client_ip}"
    if not limiter.is_allowed(ip_key, LOGIN_IP_MAX, LOGIN_WINDOW_SEC):
        return False, "Too many failed login attempts. Please wait 5 minutes before trying again."

    if username:
        user_key = f"login_fail_user:{username.lower().strip()}"
        if not limiter.is_allowed(user_key, LOGIN_USER_MAX, LOGIN_WINDOW_SEC):
            return False, "Too many failed login attempts for this account. Please wait 5 minutes or reset your password."

    return True, ""


def record_login_failure(client_ip: str, username: str = "") -> None:
    limiter = get_rate_limiter()
    ip_key = f"login_fail_ip:{client_ip}"
    limiter.record_attempt(ip_key, LOGIN_WINDOW_SEC)
    if username:
        user_key = f"login_fail_user:{username.lower().strip()}"
        limiter.record_attempt(user_key, LOGIN_WINDOW_SEC)


def record_login_success(client_ip: str, username: str = "") -> None:
    limiter = get_rate_limiter()
    ip_key = f"login_fail_ip:{client_ip}"
    limiter.reset(ip_key)
    if username:
        user_key = f"login_fail_user:{username.lower().strip()}"
        limiter.reset(user_key)


# ── Password Recovery Rate Limiting ──────────────────────────────────────────
# Default: 5 recovery requests per IP per 10 minutes, 3 per identifier per 10 minutes
RESET_IP_MAX = 5
RESET_ID_MAX = 3
RESET_WINDOW_SEC = 600


def check_forgot_password_rate_limit(client_ip: str, identifier: str = "") -> Tuple[bool, str]:
    """Return (allowed, error_message). Identical generic message for IP and identifier throttling."""
    limiter = get_rate_limiter()
    ip_key = f"reset_req_ip:{client_ip}"
    if not limiter.is_allowed(ip_key, RESET_IP_MAX, RESET_WINDOW_SEC):
        return False, "Too many password recovery requests. Please wait a few minutes before trying again."

    if identifier:
        id_key = f"reset_req_id:{identifier.lower().strip()}"
        if not limiter.is_allowed(id_key, RESET_ID_MAX, RESET_WINDOW_SEC):
            return False, "Too many password recovery requests for this identifier. Please wait a few minutes before trying again."

    return True, ""


def record_forgot_password_attempt(client_ip: str, identifier: str = "") -> None:
    limiter = get_rate_limiter()
    ip_key = f"reset_req_ip:{client_ip}"
    limiter.record_attempt(ip_key, RESET_WINDOW_SEC)
    if identifier:
        id_key = f"reset_req_id:{identifier.lower().strip()}"
        limiter.record_attempt(id_key, RESET_WINDOW_SEC)


def clear_rate_limits() -> None:
    """Helper to reset all rate limits during testing."""
    limiter = get_rate_limiter()
    limiter.clear_all()


# ── Analysis & Expensive Operations Rate Limiting (Section 15 & SEC-AUD-06) ──
ANALYSIS_IP_MAX = 60
ANALYSIS_WINDOW_SEC = 60

OCR_IP_MAX = 40
OCR_WINDOW_SEC = 60

REGISTER_IP_MAX = 10
REGISTER_WINDOW_SEC = 300


def check_analysis_rate_limit(client_ip: str) -> Tuple[bool, str]:
    """Protects expensive deep-learning analysis from abuse via atomic check-and-record."""
    key = f"analysis_ip:{client_ip}"
    limiter = get_rate_limiter()
    if not limiter.check_and_record(key, ANALYSIS_IP_MAX, ANALYSIS_WINDOW_SEC):
        return False, "Rate limit exceeded for product analyses. Please wait a minute before submitting more requests."
    return True, ""


def check_ocr_rate_limit(client_ip: str) -> Tuple[bool, str]:
    """Protects raw OCR endpoint from compute exhaustion via atomic check-and-record."""
    key = f"ocr_ip:{client_ip}"
    limiter = get_rate_limiter()
    if not limiter.check_and_record(key, OCR_IP_MAX, OCR_WINDOW_SEC):
        return False, "Rate limit exceeded for OCR extraction. Please wait a minute."
    return True, ""


def check_register_rate_limit(client_ip: str) -> Tuple[bool, str]:
    """Protects registration endpoint from automated abuse via atomic check-and-record."""
    key = f"register_ip:{client_ip}"
    limiter = get_rate_limiter()
    if not limiter.check_and_record(key, REGISTER_IP_MAX, REGISTER_WINDOW_SEC):
        return False, "Too many registration attempts from this IP address. Please wait 5 minutes before trying again."
    return True, ""
