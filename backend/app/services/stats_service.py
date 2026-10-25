"""첫 화면·머리말에 작게 보여 주는 가입자 수와 성비 (2026-10-05).

- total: 지금까지 가입한 모든 계정 수 (정지·탈퇴한 계정도 센다. 관리자 대시보드의 "전체 가입자"와 같은 숫자)
- 성비: 탈퇴하지 않은 전체 가입자의 남녀 비율 (2026-10-25 변경. 예전: 활성 사용자 = 사진 검수 완료 + 최근 7일 접속.
  관리자 대시보드 원그래프는 그대로 활성 사용자 기준)
- 로그인 없이 누구나 부르는 숫자라서 5분 동안 기억해 두고 같은 값을 돌려준다 (서버 부담을 줄이려고).
- 성비는 "여자를 1로 놓았을 때 남자가 몇인지"(male_per_female, 소수 첫째 자리)로 보낸다. 예: 1.2 → "여 1 : 남 1.2"
  여자가 0명이면 계산할 수 없으므로 None (화면에서 성비 줄을 숨김).
- 막대 그래프용으로 여자 퍼센트(female_pct)도 함께 보낸다. 남녀 인원 자체는 공개하지 않는다.
"""

import threading
import time
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.profile import PublicProfile
from app.models.user import User
from app.services.profile_service import count

CACHE_SECONDS = 300

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None}


def _compute(db: Session) -> dict:
    def member_gender(gender: str) -> int:
        """탈퇴하지 않은 가입자 (사진 검수·접속 여부·정지와 상관없이)"""
        q = (
            db.query(User.id)
            .join(PublicProfile, PublicProfile.user_id == User.id)
            .filter(
                User.deleted_at.is_(None),
                User.status != "DELETED",
                PublicProfile.gender == gender,
            )
        )
        return count(db, q)

    male = member_gender("MALE")
    female = member_gender("FEMALE")
    active = male + female
    # 여자가 0명이면 "여 1 : 남 ?"를 계산할 수 없으므로 비율을 보내지 않는다 (화면에서 성비 줄을 숨김)
    has_ratio = female > 0
    return {
        "total": count(db, db.query(User.id)),
        "male_per_female": round(male / female, 1) if has_ratio else None,
        "female_pct": round(female / active * 100) if has_ratio else None,
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
