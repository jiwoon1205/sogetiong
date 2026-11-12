"""VIP 이용권 (2026-10-03 정식 규칙, 2026-10-04 구독제: 6,000원, 기본 이용권 포함. 2026-10-06: 정식 2주, 베타 기간 구매 4주).

기간 계산(vip_until·member_until)은 membership_service.add_vip에 있다.

누가 VIP인가: users.vip_until이 지금보다 뒤인 사람 + VIP_TEST_EMAILS 테스트 계정.
VIP 혜택 5가지
  1. 하루 LIKE 10개 (무료 5개). "나를 LIKE한 사람" 우대는 보낸 사람의 하루 처음 5개 LIKE에만
  2. 내가 PASS한 사람이 24시간 뒤 다시 나옴 (무료 48시간)
  3. 나를 LIKE한 사람 목록 ("받은 LIKE" 탭)
  4. 사진 재검토 간격 3일 (무료 7일)
  5. 남이 나를 PASS하면 그날(한국 시간 자정까지)만 숨겨짐 (무료는 48시간)
VIP가 끝나면 바로 무료 규칙으로 돌아간다 (모두 그때그때 vip_until로 판단).
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, kst_today, utcnow
from app.models.user import User


def gender_of(user: User) -> str | None:
    """이 사람의 성별 (MALE / FEMALE). 프로필이 없으면(탈퇴) 탈퇴할 때 남겨 둔 성별. 성별은 가입 뒤 절대 바뀌지 않는다 (2026-11-07)."""
    profile = getattr(user, "public_profile", None)
    if profile is not None and profile.gender:
        return profile.gender
    return getattr(user, "deleted_gender", None)


def is_female_free(user: User) -> bool:
    """여성 회원 무료인가 (2026-11-07, 상시). 기본 이용권 없이 기본 이용권 혜택을 쓰고, VIP는 VIP_PRICE_FEMALE원."""
    return get_settings().female_free and gender_of(user) == "FEMALE"


def is_vip_tester(user: User) -> bool:
    """영구 무료 VIP인가? = VIP 테스트 계정(설정 VIP_TEST_EMAILS에 적힌 학교 메일) 또는 슈퍼 VIP (2026-10-12).
    이용권 없이 항상 이용·VIP 혜택·"내 이용권" 칸 숨김·하루 매칭 한도 제외가 모두 같다."""
    if getattr(user, "super_vip", False):
        return True
    return (user.email or "").strip().lower() in get_settings().vip_test_email_set


def is_test_account(user: User) -> bool:
    """운영자 테스트 계정인가? (VIP_TEST_EMAILS에 적힌 메일. 슈퍼 VIP는 실제 학생이라 아님, 2026-10-24)
    아직 열지 않은 학교의 사람을 추천에서 볼 수 있다 (profile_service.visible_university_ids)."""
    return (user.email or "").strip().lower() in get_settings().vip_test_email_set


def has_paid_vip(user: User, now: datetime | None = None) -> bool:
    """돈을 내고 산 VIP 기간이 남아 있나 (테스트 계정 제외).

    유료 시작(OPEN_AT) 전에 산 VIP도 산 순간부터 바로 쓴다 (2026-10-06, membership_service.add_vip).
    """
    until = as_utc(user.vip_until)
    return until is not None and until > (now or utcnow())


def is_vip(user: User) -> bool:
    return has_paid_vip(user) or is_vip_tester(user)


def vip_user_ids(db: Session) -> set[uuid.UUID]:
    """지금 VIP인 사람 전부 (혜택 5: 이 사람들을 PASS하면 그날만 숨겨진다)."""
    emails = get_settings().vip_test_email_set
    conditions = [User.vip_until > utcnow(), User.super_vip.is_(True)]
    if emails:
        conditions.append(func.lower(User.email).in_(emails))
    return {r[0] for r in db.query(User.id).filter(or_(*conditions))}


def feature_visible(user: User) -> bool:
    """"받은 LIKE" 탭을 보여줄까?

    VIP 판매 중(VIP_ENABLED)이거나, 판매 전 미리 보기(VIP_PREVIEW, 2026-10-04)면 모든 사람에게 보여준다.
    미리 보기에서는 혜택 안내만 나오고 살 수는 없다 (profiles._vip_info의 can_buy=False).
    둘 다 꺼져 있으면 테스트 계정에만.
    """
    s = get_settings()
    return s.vip_enabled or s.vip_preview or is_vip_tester(user)


def bonus_likes_today(user: User) -> int:
    """관리자가 준 오늘만 쓰는 추가 좋아요 (2026-10-10). 날짜가 오늘(한국 시간)이 아니면 0."""
    return (user.bonus_likes or 0) if user.bonus_likes_date == kst_today() else 0


def base_like_limit(user: User) -> int:
    """VIP가 아닐 때의 하루 LIKE 수 = 기본 이용권 5개, 여성 무료 이용은 3개 (2026-11-07)."""
    s = get_settings()
    if is_female_free(user) and not has_paid_vip(user) and not is_vip_tester(user):
        return s.female_daily_like_limit
    return s.daily_like_limit


def daily_like_limit(user: User) -> int:
    """오늘 보낼 수 있는 LIKE 수 = 기본(5 / 여성 무료 3 / VIP 10) + 관리자가 준 오늘 추가분."""
    s = get_settings()
    base = s.vip_daily_like_limit if is_vip(user) else base_like_limit(user)
    return base + bonus_likes_today(user)


def pass_cooldown_hours(user: User) -> int:
    s = get_settings()
    return s.vip_pass_cooldown_hours if is_vip(user) else s.pass_cooldown_hours


def photo_resubmit_days(user: User) -> int:
    s = get_settings()
    return s.vip_photo_resubmit_days if is_vip(user) else s.photo_resubmit_days


def price(user: User | None = None) -> int:
    """VIP 가격 (기본 포함). 할인 없음 (2026-10-04). 여성 회원은 VIP_PRICE_FEMALE원 (2026-11-07)."""
    s = get_settings()
    if user is not None and is_female_free(user):
        return s.vip_price_female
    return s.vip_price


# ---------- VIP 재구매 할인 (2026-11-12, `VIP 재구매 할인 (2026-11-12)`) ----------
# VIP를 돈 내고 산 적 있는 사람이 VIP가 끝나기 3일 전 ~ 끝난 뒤 3일 안에 다시 사면 1,000원 할인 (남녀 같음).
# 끝나기 전에 사면 새 VIP는 지금 VIP가 끝난 뒤에 이어진다 (membership_service.add_vip).
# 알림: 끝나기 2일 전 "곧 끝나요", 끝난 다음 날 "끝났어요" (한국 시간 9시~22시, send_renewal_reminders).

RENEWAL_NOTICE = "VIP_RENEWAL"  # 알림 종류 (누르면 받은 LIKE 탭)


def has_bought_vip(db: Session, user_id: uuid.UUID) -> bool:
    """VIP를 돈 내고 산 적이 있나 (입금 확인된 VIP 결제). 여성 전환·관리자 지급으로 받은 VIP는 해당 없음."""
    from app.models.payment import Payment

    return (
        db.query(Payment.id)
        .filter(Payment.user_id == user_id, Payment.kind == "VIP", Payment.status == "CONFIRMED")
        .first()
        is not None
    )


def renewal_deadline(db: Session, user: User, now: datetime | None = None) -> datetime | None:
    """지금 VIP 재구매 할인을 받을 수 있으면 할인이 끝나는 시각(VIP가 끝나고 N일 뒤), 아니면 None."""
    s = get_settings()
    if s.vip_renewal_discount <= 0 or is_vip_tester(user):
        return None
    until = as_utc(user.vip_until)
    if until is None:
        return None
    now = now or utcnow()
    window = timedelta(days=s.vip_renewal_window_days)
    if not (until - window <= now <= until + window):
        return None
    if not has_bought_vip(db, user.id):
        return None
    return until + window


def renewal_discount(db: Session, user: User, now: datetime | None = None) -> int:
    return get_settings().vip_renewal_discount if renewal_deadline(db, user, now) else 0


def _reminder_id(user_id: uuid.UUID, until: datetime, stage: str) -> uuid.UUID:
    """같은 VIP 기간·같은 단계 알림을 두 번 보내지 않으려고 쓰는 고정 번호."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"vip-renewal:{user_id}:{until.isoformat()}:{stage}")


def send_renewal_reminders(db: Session, now: datetime | None = None) -> int:
    """VIP 재구매 알림을 보낸다 (서버가 VIP_REMINDER_INTERVAL_MINUTES분마다 부름). 보낸 알림 수를 돌려준다.

    - 끝나기 VIP_REMINDER_DAYS_BEFORE일 전부터 끝나기 전까지: "VIP가 곧 끝나요"
    - 끝난 뒤 할인 기간 안: "VIP가 끝났어요"
    한국 시간 9시~22시에만 보낸다. 같은 기간·같은 단계는 한 번만. 이미 "입금했어요"를 눌렀으면 보내지 않는다.
    """
    from app.core.time import KST
    from app.models.payment import Payment
    from app.services import push_service
    from app.services.notification_service import notify
    from app.models.matching import Notification

    s = get_settings()
    if s.vip_renewal_discount <= 0:
        return 0
    now = now or utcnow()
    if not (9 <= now.astimezone(KST).hour < 22):
        return 0
    window = timedelta(days=s.vip_renewal_window_days)
    before = timedelta(days=s.vip_reminder_days_before)
    rows = (
        db.query(User)
        .filter(
            User.status == "ACTIVE",
            User.deleted_at.is_(None),
            User.vip_until.isnot(None),
            User.vip_until > now - window,
            User.vip_until <= now + before,
        )
        .all()
    )
    sent = 0
    for user in rows:
        until = as_utc(user.vip_until)
        if until is None or is_vip_tester(user) or not has_bought_vip(db, user.id):
            continue
        waiting = (
            db.query(Payment.id)
            .filter(Payment.user_id == user.id, Payment.kind == "VIP", Payment.status == "REQUESTED")
            .first()
        )
        if waiting is not None:
            continue
        stage = "ending" if now < until else "ended"
        rid = _reminder_id(user.id, until, stage)
        exists = (
            db.query(Notification.id)
            .filter(Notification.user_id == user.id, Notification.type == RENEWAL_NOTICE, Notification.related_id == rid)
            .first()
        )
        if exists is not None:
            continue
        end_day = until.astimezone(KST)
        deadline = (until + window).astimezone(KST)
        off = f"{s.vip_renewal_discount:,}원"
        if stage == "ending":
            title = "VIP가 곧 끝나요"
            body = (
                f"VIP가 {end_day.month}월 {end_day.day}일 밤 12시에 끝나요. 지금 연장하면 {off} 할인돼요. "
                f"새 VIP는 지금 VIP가 끝난 뒤 이어져요."
            )
            kind = push_service.VIP_ENDING
        else:
            title = "VIP가 끝났어요"
            body = f"{deadline.month}월 {deadline.day}일까지 VIP를 다시 사면 {off} 할인돼요."
            kind = push_service.VIP_ENDED
        notify(db, user.id, RENEWAL_NOTICE, title, body, rid)
        push_service.queue(db, user.id, kind, None)
        sent += 1
    db.commit()
    return sent
