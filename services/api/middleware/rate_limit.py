"""Rate Limiting Middleware for MUFNS (Phase 2I-2).

Implements client-IP sliding window rate limiting to protect public flood
endpoints from denial-of-service and abusive traffic during high-load monsoon events.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window in-memory rate limiter per IP address."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 180,
        burst_allowance: int = 30,
        exempt_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_limit = requests_per_minute + burst_allowance
        self.window_seconds = 60.0
        self.exempt_paths = set(exempt_paths or ["/health", "/metrics", "/docs", "/openapi.json"])
        # Map IP -> list of timestamps
        self._clients: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(ex) for ex in self.exempt_paths):
            return await call_next(request)

        # Determine client IP (handles X-Forwarded-For if behind reverse proxy)
        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        now = time.time()
        window_start = now - self.window_seconds

        # Prune older timestamps
        timestamps = self._clients[client_ip]
        self._clients[client_ip] = [t for t in timestamps if t > window_start]
        current_count = len(self._clients[client_ip])

        remaining = max(0, self.burst_limit - current_count - 1)
        reset_time = int(window_start + self.window_seconds - now) + 1

        if current_count >= self.burst_limit:
            logger.warning("Rate limit exceeded for IP", client_ip=client_ip, path=path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too Many Requests: Rate limit exceeded. Please back off.",
                    "limit_per_minute": self.requests_per_minute,
                    "retry_after_seconds": reset_time,
                },
                headers={
                    "X-RateLimit-Limit": str(self.burst_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time),
                },
            )

        self._clients[client_ip].append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.burst_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response
