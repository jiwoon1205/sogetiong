"""공지 팝업 (2026-10-05 한 번만, 2026-10-06 하루 한 번 공지 추가).

- 한 번만 보여주는 공지: CURRENT. 사용자가 "확인"을 누르면 users.announcement_seen에 그 이름을 적고,
  그 뒤로는 어느 기기에서 로그인해도 다시 뜨지 않는다.
- 하루 한 번 공지 (2026-10-06): 결제 시스템 오픈 안내. 이름에 한국 날짜를 붙인다 (예: payment-open:2026-10-06).
  오늘 "확인"을 누르면 오늘은 안 뜨고, 날짜가 바뀌면 이름이 달라져서 다시 한 번 뜬다.
  2026-10-07: 한국 시간 오후 3시(PAYMENT_DAILY_REPEAT_HOUR)부터는 이름에 "-15"를 붙여 (예: payment-open:2026-10-07-15)
  오전에 이미 본 사람에게도 한 번 더 뜬다. 오후 3시 뒤에 처음 들어온 사람은 한 번만 본다.
  보여주는 동안: 이용권 판매 중(MEMBERSHIP_ENABLED) + 정식 배포(OPEN_AT) 전.
  안 보여주는 사람: 이미 이용권·VIP를 산 사람, 운영자 테스트 계정.
  하루 공지가 떠 있는 동안에는 CURRENT보다 먼저 보여준다.
- 화면 내용은 web/src/components/AnnouncementModal.tsx (이름 또는 이름 앞부분으로 찾는다).
- 새 한 번 공지를 하려면 CURRENT 이름을 바꾼다. 끄려면 None.
"""

from datetime import datetime

from app.core.time import KST, kst_today, utcnow
from app.models.user import User
from app.services import membership_service, vip_service

# 휴대폰 알림 출시 공지 (한 번만)
CURRENT: str | None = "push-alerts-2026-10"

# 결제 시스템 오픈 공지 (하루 한 번, 정식 배포 전까지)
PAYMENT_DAILY_PREFIX = "payment-open:"
# 이 시각(한국 시간)부터 하루 공지를 한 번 더 띄운다 (2026-10-07). None이면 하루 한 번만
PAYMENT_DAILY_REPEAT_HOUR: int | None = 15


def _bought(user: User) -> bool:
    return user.member_until is not None or user.vip_until is not None or (user.member_days_banked or 0) > 0


def daily_payment_key(user: User, now: datetime | None = None) -> str | None:
    """오늘 보여줄 결제 오픈 공지 이름. 보여줄 사람이 아니면 None."""
    now = now or utcnow()
    if not membership_service.sales_open() or not membership_service.before_open(now):
        return None
    if vip_service.is_vip_tester(user) or _bought(user):
        return None
    key = f"{PAYMENT_DAILY_PREFIX}{kst_today(now).isoformat()}"
    if PAYMENT_DAILY_REPEAT_HOUR is not None and now.astimezone(KST).hour >= PAYMENT_DAILY_REPEAT_HOUR:
        key += f"-{PAYMENT_DAILY_REPEAT_HOUR}"  # 오후 공지: 오전에 본 사람에게도 한 번 더
    return key


def pending(user: User, now: datetime | None = None) -> str | None:
    """아직 안 본 공지 이름. 없으면 None. 하루 공지가 먼저."""
    daily = daily_payment_key(user, now)
    if daily is not None and user.announcement_seen != daily:
        return daily
    if CURRENT is None or user.announcement_seen == CURRENT:
        return None
    # 하루 공지를 본 뒤(announcement_seen에 하루 공지 이름이 들어감)에도 한 번 공지는 이미 봤으면 다시 띄우지 않는다
    if user.announcement_seen and user.announcement_seen.startswith(PAYMENT_DAILY_PREFIX):
        return None
    return CURRENT


def is_showable(user: User, key: str, now: datetime | None = None) -> bool:
    """화면이 "봤음"으로 보낸 이름이 지금 보여줄 수 있는 공지인가."""
    return key == CURRENT or key == daily_payment_key(user, now)
