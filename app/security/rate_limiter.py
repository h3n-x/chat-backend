import time
from collections import defaultdict, deque
from typing import Dict, Optional, Union
from starlette.requests import Request
from starlette.websockets import WebSocket


def get_client_ip(connection: Union[Request, WebSocket]) -> str:
    """Extract real client IP from reverse proxy headers or socket info."""
    forwarded_for = connection.headers.get("x-forwarded-for")
    if forwarded_for:
        # First IP in the comma-separated list is the original client IP
        return forwarded_for.split(",")[0].strip()
    
    real_ip = connection.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    
    if connection.client and connection.client.host:
        return connection.client.host
        
    return "127.0.0.1"


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter by client IP and action."""

    def __init__(self):
        # Maps (ip, action) -> deque of request timestamps
        self._history: Dict[tuple[str, str], deque[float]] = defaultdict(deque)
        # Maps ip -> active websocket connection count
        self._active_connections: Dict[str, int] = defaultdict(int)

    def is_allowed(self, ip: str, action: str, limit: int, window_seconds: float = 60.0) -> bool:
        """Check if an action is allowed for an IP under the sliding window limit."""
        now = time.time()
        cutoff = now - window_seconds
        key = (ip, action)
        
        queue = self._history[key]
        
        # Purge outdated timestamps
        while queue and queue[0] < cutoff:
            queue.popleft()
            
        if len(queue) < limit:
            queue.append(now)
            return True
        return False

    def acquire_connection(self, ip: str, max_connections: int) -> bool:
        """Track active connection count and guard against connection flooding."""
        current = self._active_connections[ip]
        if current >= max_connections:
            return False
        self._active_connections[ip] = current + 1
        return True

    def release_connection(self, ip: str) -> None:
        """Release an active connection."""
        if ip in self._active_connections:
            self._active_connections[ip] = max(0, self._active_connections[ip] - 1)
            if self._active_connections[ip] == 0:
                del self._active_connections[ip]

    def get_active_connections(self, ip: str) -> int:
        return self._active_connections.get(ip, 0)

    def cleanup_stale_entries(self, max_age_seconds: float = 300.0) -> None:
        """Periodic cleanup to prevent unbounded growth of history map."""
        now = time.time()
        cutoff = now - max_age_seconds
        stale_keys = []
        
        for key, queue in list(self._history.items()):
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                stale_keys.append(key)
                
        for key in stale_keys:
            self._history.pop(key, None)


# Global singleton instance
rate_limiter = SlidingWindowRateLimiter()
