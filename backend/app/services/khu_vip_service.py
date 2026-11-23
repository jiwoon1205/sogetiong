"""친구 10명 초대하면 평생 VIP (2026-11-22 경희대생 전용으로 시작 → 2026-11-24 모든 사용자로 넓힘, 사용자 결정).

규칙
- 대상: 모든 학교의 모든 사용자 (2026-11-24부터). 공지 팝업도 모두에게 하루 한 번 (가입한 날은 빼고).
- 1명 인정: 내 초대 링크로 가입한 친구(학교 상관없음)가 사진 검수를 통과했을 때 (지금 친구 초대 보상과 같은 순간,
  슈퍼 라이크 1개도 그대로 받는다).
- 세기 시작하는 때 = 이 사람에게 평생 VIP 이벤트가 걸린 직후. 그 **전에 가입한 초대는 세지 않는다**.
  · 경희대 학생: 2026-11-22 18:25 (경희대생 전용으로 처음 걸린 때) → 그동안 모은 숫자 유지
  · 나머지 학생: 2026-11-24 00:49 (모두에게 걸린 때)
- 10명이 되면 자동으로 평생 VIP (기본 이용권 포함). 앱 알림 + 휴대폰 알림, 감사 로그 KHU_VIP_LIFETIME.
- 평생 VIP = vip_until · member_until 을 2999-12-31로.
- 마감 없음. 끝내려면 ENABLED = False (공지도 같이 꺼진다).
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time import KST, as_utc
from app.models.university import University
from app.models.user import User
from app.services import audit_service, push_service
from app.services.notification_service import notify

ENABLED = True
DOMAIN = "khu.ac.kr"
KHU_START = datetime(2026, 11, 22, 18, 25, tzinfo=KST)  # 경희대생 전용으로 걸린 때
START = datetime(2026, 11, 24, 0, 49, tzinfo=KST)  # 모두에게 걸린 때. 이 뒤에 가입한 초대만 센다
GOAL = 10
LIFETIME = datetime(2999, 12, 31, tzinfo=KST)


def _domain(db: Session, user: User) -> str | None:
    if not user.university_id:
        return None
    university = db.get(University, user.university_id)
    return university.email_domain.lower() if university else None


def is_khu(db: Session, user: User) -> bool:
    return _domain(db, user) == DOMAIN


def has_lifetime(user: User) -> bool:
    return user.vip_until is not None and as_utc(user.vip_until).year >= 2999


def eligible(db: Session, user: User) -> bool:
    """이벤트 대상인가 (정상 계정이면 누구나, 2026-11-24)."""
    return ENABLED and user.status == "ACTIVE" and user.deleted_at is None


def start_for(db: Session, user: User) -> datetime:
    """이 사람의 초대를 세기 시작하는 때 (평생 VIP가 걸린 직후)."""
    return min(KHU_START, START) if is_khu(db, user) else START


def count(db: Session, user: User) -> int:
    """인정된 초대 수: 세기 시작한 뒤 내 링크로 가입 + 사진 검수 통과 (학교 상관없음)."""
    return (
        db.query(User.id)
        .filter(
            User.referred_by_id == user.id,
            User.referral_rewarded_at.isnot(None),
            User.created_at >= start_for(db, user),
        )
        .count()
    )


def view(db: Session, user: User) -> dict | None:
    """화면(공지 팝업·설정)용. 대상이 아니면 None. since = 세기 시작한 때 (화면 안내용)."""
    if not eligible(db, user):
        return None
    return {
        "count": min(count(db, user), GOAL),
        "goal": GOAL,
        "done": has_lifetime(user),
        "since": as_utc(start_for(db, user)).isoformat(),
    }


def grant_if_due(db: Session, referrer: User, *, admin_id=None, request=None) -> bool:
    """초대 1명이 인정될 때마다 부른다. 10명이 되면 평생 VIP (commit은 호출한 쪽)."""
    if not eligible(db, referrer) or has_lifetime(referrer):
        return False
    if count(db, referrer) < GOAL:
        return False
    referrer.vip_until = LIFETIME
    referrer.member_until = LIFETIME
    notify(
        db,
        referrer.id,
        "VIP_LIFETIME",
        "평생 VIP가 됐어요 👑",
        f"친구 {GOAL}명 초대를 달성했어요. 이제 기간 없이 VIP(기본 이용권 포함)를 쓸 수 있어요.",
    )
    push_service.queue(db, referrer.id, push_service.VIP_LIFETIME, uuid.uuid4())
    audit_service.record(
        db,
        admin_id=admin_id,
        action="KHU_VIP_LIFETIME",
        target_type="USER",
        target_id=referrer.id,
        request=request,
        metadata={"invites": GOAL},
    )
    return True
