from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request

from app.config import Settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def clear(self) -> None:
        self._hits.clear()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        if limit <= 0 or window_seconds <= 0:
            return
        now = time.monotonic()
        cutoff = now - window_seconds
        hits = self._hits[key]
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail={"message": "请求过于频繁，请稍后再试。"})
        hits.append(now)


def request_identity(request: Request, user_id: str = "") -> str:
    if user_id:
        return f"user:{user_id}"
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


def check_rate_limit(
    *,
    limiter: InMemoryRateLimiter,
    request: Request,
    settings: Settings,
    bucket: str,
    limit: int,
    user_id: str = "",
) -> None:
    identity = request_identity(request, user_id)
    limiter.check(f"{bucket}:{identity}", limit, settings.rate_limit_window_seconds)
