import uuid

from sqlalchemy.orm import Session

from app.models.matching import Notification


def notify(db: Session, user_id: uuid.UUID, type_: str, title: str, body: str, related_id: uuid.UUID | None = None) -> None:
    """알림을 추가한다. commit은 호출한 쪽에서 한다."""
    db.add(Notification(user_id=user_id, type=type_, title=title, body=body, related_id=related_id))


def has_unread(db: Session, user_id: uuid.UUID, type_: str, related_id: uuid.UUID) -> bool:
    return (
        db.query(Notification.id)
        .filter(
            Notification.user_id == user_id,
            Notification.type == type_,
            Notification.related_id == related_id,
            Notification.read_at.is_(None),
        )
        .first()
        is not None
    )


def notify_match_created(db: Session, user_id: uuid.UUID, match_id: uuid.UUID) -> None:
    """매칭 알림. 서로 LIKE했을 때, 그리고 관리자가 숨김 매칭을 다시 보이게 할 때 같은 문구를 쓴다
    (사용자가 둘을 구분할 수 없게)."""
    notify(db, user_id, "MATCH_CREATED", "새로운 매칭이 생겼어요", "서로 LIKE를 보내 매칭되었습니다. 대화를 시작해보세요.", match_id)
