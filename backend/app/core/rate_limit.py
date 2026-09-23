from collections import defaultdict
from time import monotonic

from fastapi import HTTPException, status

_buckets: dict[str, list[float]] = defaultdict(list)


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = monotonic()
    cutoff = now - window_seconds
    recent = [timestamp for timestamp in _buckets[key] if timestamp > cutoff]
    if len(recent) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many requests",
        )
    recent.append(now)
    _buckets[key] = recent
