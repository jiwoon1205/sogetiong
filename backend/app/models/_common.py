import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow


def pk() -> Mapped[uuid.UUID]:
    """모든 테이블의 기본키. PostgreSQL/SQLite 모두에서 동작하는 UUID 타입."""
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
