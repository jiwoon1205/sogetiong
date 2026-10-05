"""한 번만 보여주는 공지 팝업 (2026-10-05).

- 지금 띄울 공지는 CURRENT 하나뿐이다. 사용자가 "확인"을 누르면 users.announcement_seen에 그 이름을 적고,
  그 뒤로는 어느 기기에서 로그인해도 다시 뜨지 않는다.
- 새 공지를 하려면: CURRENT 이름을 바꾸고, 화면(web/src/components/AnnouncementModal.tsx)에 같은 이름의 내용을 넣는다.
  → 이름이 바뀌면 모든 사람에게 다시 한 번 뜬다.
- 공지를 끄려면 CURRENT = None.
"""

from app.models.user import User

# 휴대폰 알림 출시 공지
CURRENT: str | None = "push-alerts-2026-10"


def pending(user: User) -> str | None:
    """아직 안 본 공지 이름. 없으면 None."""
    if CURRENT is None or user.announcement_seen == CURRENT:
        return None
    return CURRENT
