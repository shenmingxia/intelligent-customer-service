from __future__ import annotations

import os
import time
import json
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    @property
    def enabled(self) -> bool:
        return self.max_requests > 0 and self.window_seconds > 0

    def allow(self, key: str) -> tuple[bool, int]:
        if not self.enabled:
            return True, self.max_requests

        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= window_start:
            hits.popleft()

        remaining = max(self.max_requests - len(hits), 0)
        if len(hits) >= self.max_requests:
            return False, 0

        hits.append(now)
        return True, max(remaining - 1, 0)


def build_rate_limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter(
        max_requests=_read_int_env("RATE_LIMIT_REQUESTS", 60),
        window_seconds=_read_int_env("RATE_LIMIT_WINDOW_SECONDS", 60),
    )


def setup_rate_limit_middleware(app, limiter: InMemoryRateLimiter | None = None) -> None:
    limiter = limiter or build_rate_limiter()

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not limiter.enabled or not _should_limit(request):
            return await call_next(request)

        key = await _client_key(request)
        allowed, remaining = limiter.allow(key)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests, please try again later.",
                        "request_id": request.headers.get("x-request-id", ""),
                    }
                },
                headers={
                    "x-ratelimit-limit": str(limiter.max_requests),
                    "x-ratelimit-remaining": "0",
                    "retry-after": str(limiter.window_seconds),
                },
            )

        response = await call_next(request)
        response.headers["x-ratelimit-limit"] = str(limiter.max_requests)
        response.headers["x-ratelimit-remaining"] = str(remaining)
        return response


def _should_limit(request: Request) -> bool:
    return request.url.path in {"/api/chat", "/api/feedback"}


async def _client_key(request: Request) -> str:
    user_id = await _user_id_from_body(request)
    if user_id:
        return f"user:{user_id}:{request.url.path}"

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client = forwarded_for.split(",")[0].strip()
    else:
        client = request.client.host if request.client else "unknown"
    return f"ip:{client}:{request.url.path}"


async def _user_id_from_body(request: Request) -> str | None:
    if request.method != "POST":
        return None
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return None

    try:
        body = await request.body()
        payload = json.loads(body.decode("utf-8")) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    if user_id is None:
        return None
    user_id = str(user_id).strip()
    return user_id or None


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
