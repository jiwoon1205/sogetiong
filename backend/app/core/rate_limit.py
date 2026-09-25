"""간단한 메모리 기반 요청 횟수 제한.

주의: 서버를 재시작하면 초기화되고 서버가 여러 대면 서로 공유되지 않는다.
사용자가 늘면 Redis 기반으로 교체한다 (설계도 §49).
"""

from collections import defaultdict
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        recent = [t for t in _buckets[key] if t > cutoff]
        if len(recent) >= limit:
            _buckets[key] = recent
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
            )
        recent.append(now)
        _buckets[key] = recent


def reset_rate_limits() -> None:
    """테스트용."""
    with _lock:
        _buckets.clear()
