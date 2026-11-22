"""경희대생 전용 이벤트: 경희대 친구 10명 초대하면 평생 VIP (2026-11-22, 사용자 결정).

규칙
- 대상: 경희대 학생(khu.ac.kr)만. 공지 팝업도 경희대 학생에게만 뜬다.
- 1명 인정: 내 초대 링크로 가입한 **경희대 학생**이 사진 검수를 통과했을 때 (지금 친구 초대 보상과 같은 순간,
  슈퍼 라이크 1개도 그대로 받는다).
- 이벤트 시작(START) **전에 가입한 초대는 세지 않는다** (이미 초대한 사람은 제외).
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
START = datetime(2026, 11, 22, 18, 25, tzinfo=KST)  # 사용자 결정 시각. 이 뒤에 가입한 초대만 센다
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
    """이벤트 대상인가 (경희대 학생 · 정상 계정)."""
    return ENABLED and user.status == "ACTIVE" and user.deleted_at is None and is_khu(db, user)


def count(db: Session, user: User) -> int:
    """인정된 초대 수: 이벤트 시작 뒤 내 링크로 가입 + 사진 검수 통과 + 경희대 학생."""
    khu_ids = [u for (u,) in db.query(University.id).filter(University.email_domain == DOMAIN)]
    if not khu_ids:
        return 0
    return (
        db.query(User.id)
        .filter(
            User.referred_by_id == user.id,
            User.referral_rewarded_at.isnot(None),
            User.created_at >= START,
            User.university_id.in_(khu_ids),
        )
        .count()
    )


def view(db: Session, user: User) -> dict | None:
    """화면(공지 팝업·설정)용. 대상이 아니면 None."""
    if not eligible(db, user):
        return None
    return {"count": min(count(db, user), GOAL), "goal": GOAL, "done": has_lifetime(user)}


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
        f"경희대 친구 {GOAL}명 초대를 달성했어요. 이제 기간 없이 VIP(기본 이용권 포함)를 쓸 수 있어요.",
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
