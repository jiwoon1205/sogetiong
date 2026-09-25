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
