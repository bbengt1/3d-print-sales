"""Simple in-memory rate limiter middleware."""
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP.

    Args:
        app: ASGI application
        requests_per_minute: max requests per minute per IP (default 120)
        burst: max burst capacity (default 30)
    """

    def __init__(self, app, requests_per_minute: int = 120, burst: int = 30):
        super().__init__(app)
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.burst = burst
        self._buckets: dict[str, list[float]] = defaultdict(lambda: [float(burst), time.monotonic()])

    def _get_tokens(self, key: str) -> float:
        tokens, last = self._buckets[key]
        now = time.monotonic()
        elapsed = now - last
        tokens = min(self.burst, tokens + elapsed * self.rate)
        self._buckets[key] = [tokens, now]
        return tokens

    def _consume(self, key: str) -> bool:
        tokens = self._get_tokens(key)
        if tokens >= 1:
            self._buckets[key][0] = tokens - 1
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if not self._consume(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": "10"},
            )
        response = await call_next(request)
        return response
