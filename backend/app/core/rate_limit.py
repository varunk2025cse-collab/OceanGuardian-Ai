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
import logging as _log
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings

logger = _log.getLogger(__name__)

try:
    import redis
except ImportError:  # redis is optional
    redis = None

if settings.rate_limit_backend == "memory":
    logger.warning(
        "Rate limiter is single-process in-memory. "
        "In a multi-worker deployment, each worker enforces its own independent limit. "
        "For cluster-safe rate limiting, set RATE_LIMIT_BACKEND=redis and configure REDIS_URL."
    )

_redis_client = None


def _get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if settings.rate_limit_backend != "redis" or not settings.redis_url:
        return None
    if redis is None:
        logger.warning(
            "RATE_LIMIT_BACKEND=redis configured but redis package is not installed. "
            "Falling back to in-memory rate limiting."
        )
        return None
    try:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        logger.exception(
            "Failed to initialize Redis rate limit backend; falling back to in-memory limiter."
        )
        _redis_client = None
    return _redis_client


def _redis_exceeded(key: str, limit_value: int) -> bool:
    client = _get_redis_client()
    if client is None:
        return False
    now = time.time()
    window = _WINDOW_SECONDS
    redis_key = f"rate_limit:{key}"
    try:
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, int(window) + 2)
        _, _, count, _ = pipe.execute()
        return count >= limit_value
    except Exception:
        logger.exception(
            "Redis rate limiter failed; falling back to in-memory rate limiting for this request."
        )
        return False

_buckets: dict[str, deque] = defaultdict(deque)
_WINDOW_SECONDS = 60.0


def rate_limit(key_prefix: str, limit: int | None = None):
    def dependency(request: Request) -> None:
        if settings.environment == "test":
            return
        limit_value = limit if limit is not None else settings.rate_limit_per_minute
        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}"

        if settings.rate_limit_backend == "redis" and settings.redis_url:
            if _redis_exceeded(key, limit_value):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests — please wait a moment and try again.",
                )
            return

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
