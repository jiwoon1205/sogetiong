import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk


class PushSubscription(Base):
    """휴대폰(브라우저) 알림을 보낼 주소 (2026-10-05, 마이그레이션 0019). 기기(브라우저) 하나당 한 줄.

    - endpoint: 구글·애플·모질라 같은 "알림 배달 회사"의 주소. 서버는 여기에 암호화한 알림을 보낸다.
    - p256dh, auth: 그 브라우저만 풀 수 있게 알림을 암호화하는 열쇠 (배달 회사는 내용을 못 본다).
    - session_id: 이 기기에서 로그인한 세션. 로그아웃·비밀번호 변경·탈퇴·정지로 세션이 지워지면
      DB가 이 줄도 같이 지운다(ON DELETE CASCADE) → 로그아웃한 휴대폰으로 알림이 가지 않는다.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = created_at()
    # 마지막으로 알림이 잘 배달된 시각 (관리·문제 확인용)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
