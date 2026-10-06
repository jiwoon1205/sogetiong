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
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.models.user import User


def is_vip_tester(user: User) -> bool:
    """VIP 테스트 계정인가? (설정 VIP_TEST_EMAILS에 적힌 학교 메일)"""
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
    conditions = [User.vip_until > utcnow()]
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


def daily_like_limit(user: User) -> int:
    s = get_settings()
    return s.vip_daily_like_limit if is_vip(user) else s.daily_like_limit


def pass_cooldown_hours(user: User) -> int:
    s = get_settings()
    return s.vip_pass_cooldown_hours if is_vip(user) else s.pass_cooldown_hours


def photo_resubmit_days(user: User) -> int:
    s = get_settings()
    return s.vip_photo_resubmit_days if is_vip(user) else s.photo_resubmit_days


def price() -> int:
    """VIP 가격 (기본 포함). 할인 없음 (2026-10-04)."""
    return get_settings().vip_price
