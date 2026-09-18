import time
from starlette.requests import Request
from app.security.rate_limiter import SlidingWindowRateLimiter, get_client_ip


def test_sliding_window_limiter():
    limiter = SlidingWindowRateLimiter()
    ip = "192.168.1.100"
    action = "test_action"
    limit = 3
    window = 1.0  # 1 second window

    # First 3 should succeed
    assert limiter.is_allowed(ip, action, limit, window) is True
    assert limiter.is_allowed(ip, action, limit, window) is True
    assert limiter.is_allowed(ip, action, limit, window) is True

    # 4th should be blocked
    assert limiter.is_allowed(ip, action, limit, window) is False

    # Wait for window to pass
    time.sleep(1.05)

    # Should be allowed again
    assert limiter.is_allowed(ip, action, limit, window) is True


def test_connection_tracking():
    limiter = SlidingWindowRateLimiter()
    ip = "10.0.0.1"
    max_conn = 2

    assert limiter.acquire_connection(ip, max_conn) is True
    assert limiter.acquire_connection(ip, max_conn) is True
    # Exceeded max
    assert limiter.acquire_connection(ip, max_conn) is False

    # Release one
    limiter.release_connection(ip)
    assert limiter.acquire_connection(ip, max_conn) is True


def test_client_ip_extraction():
    # Scenario 1: X-Forwarded-For with multiple IPs
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18, 150.172.238.178")],
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    assert get_client_ip(req) == "203.0.113.195"

    # Scenario 2: X-Real-IP
    scope2 = {
        "type": "http",
        "headers": [(b"x-real-ip", b"198.51.100.2")],
        "client": ("127.0.0.1", 12345),
    }
    req2 = Request(scope2)
    assert get_client_ip(req2) == "198.51.100.2"

    # Scenario 3: Fallback to socket client host
    scope3 = {
        "type": "http",
        "headers": [],
        "client": ("172.16.0.5", 54321),
    }
    req3 = Request(scope3)
    assert get_client_ip(req3) == "172.16.0.5"


def test_stale_entries_cleanup():
    limiter = SlidingWindowRateLimiter()
    ip = "192.168.1.50"
    limiter.is_allowed(ip, "test_action", 10, window_seconds=60)
    assert (ip, "test_action") in limiter._history

    # Cleanup with 0 max age should clear it
    limiter.cleanup_stale_entries(max_age_seconds=0.0)
    assert (ip, "test_action") not in limiter._history


def test_get_active_connections():
    limiter = SlidingWindowRateLimiter()
    ip = "192.168.1.55"
    assert limiter.get_active_connections(ip) == 0
    limiter.acquire_connection(ip, 5)
    assert limiter.get_active_connections(ip) == 1
    limiter.release_connection(ip)
    assert limiter.get_active_connections(ip) == 0

