"""
Minimal in-memory rate limiting (docs/SECURITY.md, V2 core build Phase 21).

Deliberately NOT applied to safety-critical endpoints. SOS trigger in
particular must never be throttled — a fisherman's retry storm during a
real emergency is exactly the traffic this system exists to accept, not
block. Rate limiting here protects the login/register surface from
brute-force and spam, which is a different threat model.

Implementation note: this is a single-process, in-memory sliding window.
It is intentionally simple rather than distributed (no Redis dependency
added for this). If OceanGuardian is ever deployed with multiple API
worker processes/instances behind a load balancer, each process enforces
its own independent limit — documented as a known limitation in
docs/SECURITY.md, not silently pretended to be cluster-safe.

Disabled entirely when settings.environment == "test" so the test suite
(which legitimately registers hundreds of users per run from one process)
isn't throttled — this is standard practice, not a weakened assertion.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings

_buckets: dict[str, deque] = defaultdict(deque)
_WINDOW_SECONDS = 60.0


def rate_limit(key_prefix: str, limit: int | None = None):
    def dependency(request: Request) -> None:
        if settings.environment == "test":
            return
        limit_value = limit if limit is not None else settings.rate_limit_per_minute
        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}"
        now = time.monotonic()
        bucket = _buckets[key]
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit_value:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — please wait a moment and try again.",
            )
        bucket.append(now)

    return dependency
