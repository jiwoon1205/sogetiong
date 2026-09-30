"""운영진에게 보내는 알림 메일 (새 사진 검수 대기, 새 신고).

- 받는 사람: 해당 일을 할 권한이 있는 활성 관리자 (최고 관리자는 항상 포함)
- 메일에는 사용자 정보(닉네임·이메일)를 넣지 않는다. 관리자 화면 링크만 보낸다.
- 새 사진 알림은 검수 대기 사진이 photo_alert_threshold장(기본 10장) 쌓였을 때 한 번 보낸다.
  검수해서 대기 사진이 다시 그 아래로 줄면, 다음에 또 10장이 쌓일 때 다시 보낸다.
  (서버 메모리에 "이번에 이미 보냈는지"를 기억한다. 서버를 재시작하면 한 번 더 갈 수 있지만 괜찮다.)
"""

import logging
from threading import Lock

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.admin import SUPER_ADMIN_ROLE, AdminUser
from app.models.photo import UserPhoto
from app.models.user import User
from app.services.email_service import EmailDeliveryError

logger = logging.getLogger(__name__)

_lock = Lock()
_backlog_alert_sent = False


def admin_emails_with(db: Session, permission: str) -> list[str]:
    emails = []
    for admin in db.query(AdminUser).filter(AdminUser.status == "ACTIVE").all():
        role = admin.role
        if role is None:
            continue
        if role.name == SUPER_ADMIN_ROLE or permission in (role.permissions_json or []):
            emails.append(admin.email)
    return emails


def photo_backlog_alert_due(pending_count: int) -> bool:
    """대기 사진 수를 보고 알림을 보낼 차례인지 정한다. 보낼 차례면 "보냈음"으로 바로 기록한다.

    - 기준(10장) 미만: 보내지 않고, "보냈음" 기록을 지운다 → 다음에 10장이 되면 다시 보냄
    - 기준 이상 + 아직 안 보냄: 보낸다
    - 기준 이상 + 이미 보냄: 또 보내지 않는다 (11장, 12장째마다 메일이 오지 않게)
    """
    global _backlog_alert_sent
    threshold = get_settings().photo_alert_threshold
    with _lock:
        if pending_count < threshold:
            _backlog_alert_sent = False
            return False
        if _backlog_alert_sent:
            return False
        _backlog_alert_sent = True
        return True


def reset_photo_alert() -> None:
    """테스트용."""
    global _backlog_alert_sent
    with _lock:
        _backlog_alert_sent = False


def pending_photo_query(db: Session):
    """검수할 사진 묶음: 대기 + 확인 중, 활성 계정만 (정지·탈퇴한 사람의 사진은 검수하지 않는다).

    여러 장을 함께 낸 경우 대표 사진(position 0)만 센다 → 대기열·알림 수 = 제출 묶음 수.
    """
    return (
        db.query(UserPhoto)
        .join(User, User.id == UserPhoto.user_id)
        .filter(
            UserPhoto.review_status.in_(["PENDING", "IN_REVIEW"]),
            UserPhoto.upload_status != "DELETED",
            UserPhoto.position == 0,
            User.status == "ACTIVE",
        )
    )


def send_all(send, recipients: list[str], *args) -> None:
    """백그라운드에서 여러 관리자에게 보낸다. 한 명에게 실패해도 나머지는 계속."""
    for email in recipients:
        try:
            send(email, *args)
        except EmailDeliveryError:
            logger.error("admin alert email failed: %s", getattr(send, "__name__", "unknown"))
