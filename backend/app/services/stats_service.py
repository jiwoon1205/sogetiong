"""첫 화면·머리말에 작게 보여 주는 가입자 수와 성비 (2026-10-05).

- total: 지금까지 가입한 모든 계정 수 (정지·탈퇴한 계정도 센다. 관리자 대시보드의 "전체 가입자"와 같은 숫자)
- 성비: "활성 사용자"의 남녀 비율 (관리자 대시보드 원그래프와 같은 기준)
  활성 사용자 = 사진 검수 완료 + 최근 7일(오늘 포함) 안에 접속한 정상 계정
- 로그인 없이 누구나 부르는 숫자라서 5분 동안 기억해 두고 같은 값을 돌려준다 (서버 부담을 줄이려고).
- 사람 수는 퍼센트로만 알려 준다 (활성 남녀 인원 자체는 공개하지 않는다).
"""

import threading
import time
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import kst_today
from app.models.photo import UserPhoto
from app.models.profile import PublicProfile
from app.models.user import User, UserDailyVisit
from app.services.profile_service import count

CACHE_SECONDS = 300

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None}


def _compute(db: Session) -> dict:
    week_start = kst_today() - timedelta(days=6)
    approved = db.query(UserPhoto.user_id).filter(UserPhoto.review_status == "APPROVED")
    visitors = db.query(UserDailyVisit.user_id).filter(UserDailyVisit.visit_date >= week_start)

    def active_gender(gender: str) -> int:
        q = (
            db.query(User.id)
            .join(PublicProfile, PublicProfile.user_id == User.id)
            .filter(
                User.status == "ACTIVE",
                PublicProfile.gender == gender,
                User.id.in_(visitors),
                User.id.in_(approved),
            )
        )
        return count(db, q)

    male = active_gender("MALE")
    female = active_gender("FEMALE")
    active = male + female
    female_pct = round(female / active * 100) if active else None
    return {
        "total": count(db, db.query(User.id)),
        # 활성 사용자가 한 명도 없으면 비율을 보내지 않는다 (화면에서 성비 줄을 숨김)
        "female_pct": female_pct,
        "male_pct": (100 - female_pct) if female_pct is not None else None,
    }


def member_stats(db: Session) -> dict:
    if get_settings().environment == "test":  # 테스트에서는 매번 새로 센다
        return _compute(db)
    now = time.monotonic()
    with _lock:
        if _cache["value"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["value"]
    value = _compute(db)
    with _lock:
        _cache.update(at=now, value=value)
    return value
