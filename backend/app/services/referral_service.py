"""친구 초대 이벤트 (2026-10-24). 설계: 프로젝트 문서 "친구 초대 이벤트 설계 (2026-10-24)".

- 사람마다 초대 링크 코드(무작위 6글자)가 있다: private-matching.com/?ref=K7PX2M
- 이벤트 기간(REFERRAL_START ~ REFERRAL_END)에 그 링크로 가입하면 "누구의 초대인지" 기록한다.
  탈퇴 후 7일(REFERRAL_REJOIN_EXCLUDE_DAYS) 안에 다시 가입한 계정은 초대로 치지 않는다 (2026-10-24 변경, 예전: 재가입 전부 제외)
- 초대받은 사람의 사진이 처음 승인되면 초대한 사람에게 슈퍼 라이크 1개 (한 사람당 한 번만).
  기간 안에 가입했으면 승인이 기간 뒤여도 준다. 초대한 사람이 정지·탈퇴 상태면 주지 않는다.
- 초대받은 사람에게는 혜택이 없다. 누가 초대했는지 화면에 보여주지 않는다 (초대한 사람에게도 숫자만).
"""

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.models.user import User
from app.services import audit_service, super_like_service
from app.services.notification_service import notify

# 헷갈리는 글자(0·O·1·I·L) 빼고 (결제 코드와 같은 글자 모음)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def active(now: datetime | None = None) -> bool:
    """지금 이벤트 기간인가."""
    s = get_settings()
    now = now or utcnow()
    start, end = s.referral_start_utc, s.referral_end_utc
    if start is None or end is None:
        return False
    return start <= now < end


def normalize(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip().upper()
    if len(code) != CODE_LENGTH or any(c not in CODE_ALPHABET for c in code):
        return None
    return code


def code_for(db: Session, user: User) -> str:
    """내 초대 코드. 없으면 만든다 (commit은 호출한 쪽에서)."""
    if user.referral_code:
        return user.referral_code
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.query(User.id).filter(User.referral_code == code).first() is None:
            user.referral_code = code
            try:
                db.flush()
            except IntegrityError:  # 동시에 같은 코드를 만든 경우 (거의 없음)
                db.rollback()
                continue
            return code
    raise RuntimeError("초대 코드를 만들지 못했습니다")


def rejoined_recently(previous: list[User], now: datetime | None = None) -> bool:
    """예전 계정(같은 학교 메일로 가입했다가 탈퇴한 계정) 중에 최근 N일 안에 탈퇴한 것이 있나."""
    now = now or utcnow()
    days = get_settings().referral_rejoin_exclude_days
    cutoff = now - timedelta(days=days)
    for u in previous:
        if u.deleted_at is None:
            return True  # 탈퇴하지 않은 예전 계정 (보통 없음) → 안전하게 제외
        if as_utc(u.deleted_at) > cutoff:
            return True
    return False


def attach(db: Session, new_user: User, code: str | None, *, previous: list[User] | None = None) -> bool:
    """가입할 때: 이벤트 기간에 초대 링크로 가입한 사람이면 초대한 사람을 기록한다.
    previous = 같은 메일로 예전에 가입했던 계정들. 그중 7일 안에 탈퇴한 계정이 있으면 초대로 치지 않는다."""
    code = normalize(code)
    if code is None or not active() or rejoined_recently(previous or []):
        return False
    referrer = db.query(User).filter(User.referral_code == code).first()
    if referrer is None or referrer.id == new_user.id or referrer.status != "ACTIVE" or referrer.deleted_at is not None:
        return False
    new_user.referred_by_id = referrer.id
    return True


def _rewards_given(db: Session, referrer_id: uuid.UUID) -> int:
    return (
        db.query(User.id)
        .filter(User.referred_by_id == referrer_id, User.referral_rewarded_at.isnot(None))
        .count()
    )


def reward_if_due(db: Session, invitee: User, *, admin_id=None, request=None) -> bool:
    """초대받은 사람의 사진이 승인될 때 부른다. 처음 한 번만 초대한 사람에게 슈퍼 라이크 1개 (commit은 호출한 쪽)."""
    if invitee.referred_by_id is None or invitee.referral_rewarded_at is not None:
        return False
    referrer = db.get(User, invitee.referred_by_id)
    if referrer is None or referrer.status != "ACTIVE" or referrer.deleted_at is not None:
        return False
    cap = get_settings().referral_max_rewards
    if cap > 0 and _rewards_given(db, referrer.id) >= cap:
        return False
    super_like_service.add(referrer, 1)
    invitee.referral_rewarded_at = utcnow()
    notify(
        db,
        referrer.id,
        "REFERRAL_REWARD",
        "초대한 친구가 가입을 마쳤어요 🎉",
        "친구 초대 이벤트로 슈퍼 라이크 1개를 받았어요. 추천 화면의 ★ 버튼으로 보낼 수 있어요.",
    )
    audit_service.record(
        db,
        admin_id=admin_id,
        action="REFERRAL_REWARD",
        target_type="USER",
        target_id=referrer.id,
        request=request,
        metadata={"invitee_id": str(invitee.id), "super_likes_after": referrer.super_likes},
    )
    return True


def view(db: Session, user: User) -> dict:
    """설정 화면 "친구 초대" 칸. 이벤트 기간이 아니면 코드를 만들지 않는다."""
    s = get_settings()
    is_active = active()
    return {
        "active": is_active,
        "start": s.referral_start_utc.isoformat() if s.referral_start_utc else None,
        "end": s.referral_end_utc.isoformat() if s.referral_end_utc else None,
        "code": code_for(db, user) if is_active else user.referral_code,
        # 초대로 가입한 사람 수 / 그중 사진 승인까지 끝나 슈퍼 라이크를 받은 수 (누구인지는 보여주지 않는다)
        "invited": db.query(User.id).filter(User.referred_by_id == user.id).count(),
        "rewarded": _rewards_given(db, user.id),
        "max_rewards": s.referral_max_rewards,
    }
