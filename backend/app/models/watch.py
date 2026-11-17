"""감시 대상 (2026-11-17, 마이그레이션 0042). 관리자 전용 — 사용자 화면·API 어디에도 내보내지 않는다.

캐주얼한 만남을 고르지 않은 사람이 '캐주얼한 만남'을 고른 사람에게 좋아요·슈퍼 라이크를 보내면(또는 보내려다
'찾는 관계가 달라요'로 막히면) 한 줄씩 남기고, 그 사람을 감시 대상에 올린다.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.models._common import pk


class WatchEvent(Base):
    """감시 기록 한 줄 = 캐주얼한 만남을 고른 사람에게 보낸(또는 막힌) 좋아요 하나."""

    __tablename__ = "watch_events"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)  # 보낸 사람
    target_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)  # 받은 사람(캐주얼)
    actor_goal: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 그때 보낸 사람의 찾는 관계 (None = 안 고름)
    is_super: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # True = '찾는 관계가 달라요'로 막힘
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class WatchTarget(Base):
    """감시 대상 한 사람. 관리자가 상태(지켜보는 중/문제없음)와 메모를 관리한다.
    '문제없음'으로 둔 사람도 다시 캐주얼에게 좋아요를 보내면 '지켜보는 중'으로 돌아온다."""

    __tablename__ = "watch_targets"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="WATCHING", nullable=False)  # WATCHING / CLEARED
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
