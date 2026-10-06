"""이용권 (2026-10-04 구독제). 날짜 계산은 이 파일에만 둔다.

규칙 (`구독제 전환 설계`, `유료화(구독제) 코드 구현 가이드라인` 0장 D1~D10)
- 기본 이용권 4주(28일) 3,000원, VIP 4주(28일) 6,000원 = 기본 포함. 자동결제 없음.
- 끝나는 시각은 "그날 밤 12시(한국 시간)"로 올린다 (D4). 이미 밤 12시에 끝나는 기간에 붙이면 정확히 28일이 더해진다.
- 첫 이용권은 추천이 열리는 순간(승인 사진 + 등급)부터 센다 (D1). 그 전에 낸 일수는 member_days_banked에 쌓아 둔다.
- 언제든 미리 연장할 수 있다. 끝나는 날 뒤에 붙는다 (D2).
- VIP를 사면 그날부터 VIP 28일, 남아 있던 기본 기간은 VIP 뒤로 밀린다 → member_until = max(member_until, 지금) + 28일.
- 이용권이 없으면 추천·LIKE·PASS·받은 LIKE·사진 재검토만 막는다. 대화는 막지 않는다.
- 스위치(MEMBERSHIP_ENABLED)가 꺼져 있으면 모두 이용권이 있는 것으로 본다 (베타 동작 그대로).
- VIP 테스트 계정(VIP_TEST_EMAILS)은 항상 이용권 + VIP (D10).
- 유료 시작 시각 OPEN_AT (2026-10-06, 점검 기간 없앰): 그 전에는 스위치가 켜져 있어도 베타처럼 모두 무료.
  그 전에 미리 산 이용권·VIP·쌓아 둔 일수는 그 시각부터 센다. 시각이 되면 서버를 다시 켜지 않아도 자동으로 유료.
- 무료 체험 (2026-10-06, `무료 체험 플랜 설계`): 이용권이 없는 사람은 LIKE를 평생 FREE_TRIAL_LIKES(3)개만 보낼 수 있다.
  다 쓰면(또는 이용권이 끝나면) 추천·PASS·대화는 되고 LIKE만 막힌다. 이용권을 사면 체험은 끝난다.
- 가격 (2026-10-06): 정가 4,000원, MEMBERSHIP_DISCOUNT_UNTIL 전에는 할인가 3,000원.
"""

import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, kst_day_start, utcnow
from app.models.user import User
from app.services import profile_service, vip_service


def sales_open() -> bool:
    """이용권·VIP를 살 수 있나 (스위치 MEMBERSHIP_ENABLED). 유료 시작 시각 전에도 미리 살 수 있다."""
    return get_settings().membership_enabled


def enabled(now: datetime | None = None) -> bool:
    """지금 유료로 운영 중인가 = 스위치가 켜져 있고 유료 시작 시각(OPEN_AT)이 지났다.

    아니면 베타처럼 모두 무료다 (체험 제한 없음, 하루 LIKE 5개).
    """
    return sales_open() and not before_open(now)


def open_at() -> datetime | None:
    """유료 시작 시각(UTC). 없으면 스위치를 켠 순간부터 유료."""
    return get_settings().open_at_utc


def before_open(now: datetime | None = None) -> bool:
    """유료 시작 시각 전인가 (베타 기간). 점검 기간은 2026-10-06에 없앴다 — 이 시각 전에도 아무것도 막지 않는다."""
    at = open_at()
    return at is not None and (now or utcnow()) < at


def price(now: datetime | None = None) -> int:
    """지금 기본 이용권 가격. 할인 종료 시각 전이면 할인가 (2026-10-06: 정가 4,000원, 할인가 3,000원)."""
    s = get_settings()
    until = s.membership_discount_until_utc
    if until is not None and (now or utcnow()) < until:
        return s.membership_discount_price
    return s.membership_price


def _start(now: datetime) -> datetime:
    """기간을 세기 시작하는 시각 = max(지금, 오픈 시각). 점검 기간에 낸 날짜를 잃지 않게."""
    at = open_at()
    return at if at is not None and at > now else now


def _base(until: datetime | None, now: datetime) -> datetime:
    """새 기간을 붙일 기준: 남아 있는 기간의 끝, 없으면 시작 시각."""
    start = _start(now)
    return until if until is not None and until > start else start


def end_of_kst_day(t: datetime) -> datetime:
    """t가 속한 날(한국 시간)의 밤 12시. t가 정확히 밤 12시면 그대로 둔다 (하루가 더 붙지 않게)."""
    start = kst_day_start(t)
    return start if start == t else start + timedelta(days=1)


def _until(user: User) -> datetime | None:
    return as_utc(user.member_until)


def has_membership(user: User, now: datetime | None = None) -> bool:
    """지금 추천·LIKE를 쓸 수 있는 이용권이 있나."""
    now = now or utcnow()
    if not enabled(now) or vip_service.is_vip_tester(user):
        return True
    until = _until(user)
    if until is not None and until > now:
        return True
    # VIP에는 기본이 포함된다 (보통 member_until이 vip_until 이상이지만, 관리자가 줄였을 때도 안전하게)
    return vip_service.has_paid_vip(user, now)


def can_start(db: Session, user: User) -> bool:
    """추천을 볼 수 있는 상태인가 = 승인된 사진 + 최근 평가에 등급 (D1의 '추천이 열리는 순간')."""
    return profile_service.has_approved_photo(db, user.id) and profile_service.current_tier(db, user.id) is not None


def needs_first_payment(user: User, *, has_approved_photo: bool) -> bool:
    """가입 단계에서 이용권 입금을 보여줘야 하나.

    2026-10-06 무료 체험부터는 가입할 때 내지 않는다 (가입 → 사진 → 체험 LIKE → 다 쓰면 결제).
    체험을 끈 경우(FREE_TRIAL_LIKES=0)에만 예전처럼 사진을 내기 전에 낸다.
    """
    if get_settings().free_trial_likes > 0:
        return False
    if not enabled() or vip_service.is_vip_tester(user):
        return False
    return not has_approved_photo and user.member_until is None and (user.member_days_banked or 0) == 0


# ---------- 무료 체험 (2026-10-06) ----------

def trial_limit() -> int:
    return get_settings().free_trial_likes


def trial_left(user: User) -> int:
    return max(0, trial_limit() - (user.trial_likes_used or 0))


def like_access(user: User, now: datetime | None = None) -> str:
    """LIKE를 어떻게 보낼 수 있나.

    paid  = 이용권(또는 VIP·테스트 계정·베타 기간) → 하루 한도대로
    trial = 이용권 없음 + 체험 LIKE가 남음 → 평생 3개 중에서
    none  = 이용권 없음 + 체험 LIKE를 다 씀(또는 이용권이 끝남) → LIKE 불가. 추천·PASS·대화는 된다.
    """
    if has_membership(user, now):
        return "paid"
    return "trial" if trial_left(user) > 0 else "none"


def end_trial(user: User) -> None:
    """이용권을 사면 체험은 끝난다 (남은 체험 LIKE는 사라짐). 나중에 이용권이 끝나도 체험은 다시 안 생긴다."""
    user.trial_likes_used = max(user.trial_likes_used or 0, trial_limit())


def use_trial_like(db: Session, user: User) -> bool:
    """체험 LIKE 1개 쓰기. 동시에 여러 번 눌러도 한도를 넘지 않게 DB에서 조건부로 늘린다. 썼으면 True."""
    updated = (
        db.query(User)
        .filter(User.id == user.id, User.trial_likes_used < trial_limit())
        .update({User.trial_likes_used: User.trial_likes_used + 1}, synchronize_session=False)
    )
    db.refresh(user, ["trial_likes_used"])
    return updated == 1


def cannot_like_ids(db: Session, user_ids: list, now: datetime | None = None) -> set:
    """이 중에서 지금 LIKE를 보낼 수 없는 사람 (체험 다 씀·이용권 끝남). 남의 추천에서 같은 등급 안에서 뒤로 보낸다."""
    if not user_ids or not enabled(now):
        return set()
    now = now or utcnow()
    emails = get_settings().vip_test_email_set
    rows = (
        db.query(User.id, User.email, User.member_until, User.vip_until, User.trial_likes_used)
        .filter(User.id.in_(list(user_ids)))
        .all()
    )
    limit = trial_limit()
    out = set()
    for uid, email, member_until, vip_until, used in rows:
        if (email or "").strip().lower() in emails:
            continue
        if any(t is not None and as_utc(t) > now for t in (member_until, vip_until)):
            continue
        if (used or 0) < limit:
            continue
        out.add(uid)
    return out


def grant_rereview(user: User, now: datetime | None = None) -> None:
    """이용권·VIP를 살 때마다 "사진 바로 재검토 1회" (2026-10-06). 쌓이지 않고 1회로 다시 채워진다."""
    user.rereview_granted_at = now or utcnow()


def add_membership(db: Session, user: User, now: datetime | None = None, days: int | None = None) -> None:
    """기본 이용권 입금 확인. 추천이 열리기 전이면 일수를 쌓아 두고, 아니면 끝나는 날 뒤에 붙인다."""
    now = now or utcnow()
    days = days or get_settings().membership_days
    until = _until(user)
    active = until is not None and until > now
    if not active and not can_start(db, user):
        user.member_days_banked = (user.member_days_banked or 0) + days
    else:
        user.member_until = end_of_kst_day(_base(until, now) + timedelta(days=days))
    end_trial(user)


def add_vip(db: Session, user: User, now: datetime | None = None) -> None:
    """VIP 입금 확인. VIP는 지금부터, 남아 있던 기본 기간은 VIP 뒤로 밀린다 (구독제 설계 2장)."""
    now = now or utcnow()
    days = get_settings().vip_days
    vip_until = as_utc(user.vip_until)
    user.vip_until = end_of_kst_day(_base(vip_until, now) + timedelta(days=days))
    user.member_until = end_of_kst_day(_base(_until(user), now) + timedelta(days=days))
    end_trial(user)


def start_banked(db: Session, user: User, now: datetime | None = None) -> bool:
    """쌓아 둔 일수를 시작한다 (등급이 정해져 추천이 열릴 때). 시작했으면 True."""
    banked = user.member_days_banked or 0
    if banked <= 0 or not can_start(db, user):
        return False
    now = now or utcnow()
    user.member_until = end_of_kst_day(_base(_until(user), now) + timedelta(days=banked))
    user.member_days_banked = 0
    return True


def adjust(user: User, days: int, now: datetime | None = None) -> None:
    """관리자 기간 조정 (D8). 남아 있으면 끝나는 날에서 더하거나 빼고, 끝났으면 지금부터 더한다."""
    now = now or utcnow()
    until = _until(user)
    if until is not None and until > now:
        user.member_until = until + timedelta(days=days)
    elif days > 0:
        user.member_until = end_of_kst_day(_start(now) + timedelta(days=days))


def status(user: User, now: datetime | None = None) -> str:
    """화면용: none(산 적 없음) / banked(사진 검수 후 시작) / active / expired."""
    now = now or utcnow()
    until = _until(user)
    if until is not None and until > now:
        return "active"
    if (user.member_days_banked or 0) > 0:
        return "banked"
    return "expired" if until is not None else "none"


def days_left(user: User, now: datetime | None = None) -> int | None:
    """남은 날짜 (올림). 끝났거나 없으면 None."""
    now = now or utcnow()
    until = _until(user)
    if until is None or until <= now:
        return None
    return math.ceil((until - now).total_seconds() / 86400)


def view(user: User, now: datetime | None = None) -> dict:
    """/me 등에 넣는 이용권 정보."""
    s = get_settings()
    until = _until(user)
    return {
        "enabled": enabled(),
        "active": has_membership(user, now),
        "free": vip_service.is_vip_tester(user),  # 테스트 계정 (결제 없이 항상 이용)
        "status": status(user, now),
        "until": until.isoformat() if until else None,
        "days_left": days_left(user, now),
        "banked_days": user.member_days_banked or 0,
        "days": s.membership_days,
        "price": price(now),
        "regular_price": s.membership_price,
        "discount_until": s.membership_discount_until_utc.isoformat() if s.membership_discount_until_utc else None,
        "sales_open": sales_open(),
        "warn_days": s.membership_warn_days,
        # 유료 시작 시각과 지금 그 전(베타)인지
        "open_at": open_at().isoformat() if open_at() else None,
        "before_open": before_open(now),
        # 무료 체험 (2026-10-06). like_access: paid / trial / none
        "like_access": like_access(user, now),
        "trial": {"limit": trial_limit(), "used": min(user.trial_likes_used or 0, trial_limit()), "left": trial_left(user)},
    }
