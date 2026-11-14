"""대화방 사진 보내기 · 인스타 아이디 교환 (2026-11-14).

규칙은 app/services/chat_extra_service.py 맨 위 설명.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk

# 사진 보내는 방식
PHOTO_MODES = (
    "ONCE",  # 1회 보기: 받은 사람이 한 번(5초) 보면 대화창에서 사라진다
    "KEEP",  # 대화에 보관: 일반 사진처럼 계속 볼 수 있다
)

# 인스타 아이디 교환 상태
INSTA_STATUSES = ("PENDING", "ACCEPTED", "DECLINED", "CANCELLED")


class ChatPhoto(Base):
    """대화방에서 보낸 사진. 메시지 1개(message_type="PHOTO")에 사진 1장.

    - 파일은 관리자 확인(신고 처리)용으로 보낸 뒤 90일 동안 서버에 보관한다. 1회 보기 사진도 마찬가지.
      90일이 지나면 파일을 지우고 storage_key를 ""로 비운다 (신고 처리 중인 대화방은 처리가 끝날 때까지 보관).
    - 사용자는 이 파일을 내려받을 수 있는 영구 주소를 받지 않는다. 볼 때마다 서버를 거친다.
    """

    __tablename__ = "chat_photos"

    id: Mapped[uuid.UUID] = pk()
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("messages.id"), unique=True, nullable=False)
    match_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("matches.id"), nullable=False, index=True)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # PHOTO_MODES
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)  # 파일을 지우면 ""
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1회 보기 사진을 받은 사람이 연 시각. 열면 다시는 볼 수 없다
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 보관 기간(90일)이 지나 파일을 지운 시각
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()


class InstaShare(Base):
    """인스타 아이디 교환.

    - 요청하는 사람이 자기 아이디를 적고 요청 → 상대가 자기 아이디를 적고 수락하면, 그 순간 두 아이디가 서로에게 동시에 보인다.
    - 수락 전에는 요청한 사람의 아이디도 상대에게 보이지 않는다 (거절해도 아이디가 남지 않게).
    - 관리자는 신고 처리를 위해 언제든 두 아이디를 볼 수 있다.
    """

    __tablename__ = "insta_shares"

    id: Mapped[uuid.UUID] = pk()
    match_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("matches.id"), nullable=False, index=True)
    # 요청 카드가 붙는 메시지 (message_type="INSTA_REQUEST")
    request_message_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("messages.id"), unique=True, nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    requester_handle: Mapped[str] = mapped_column(String(30), nullable=False)
    responder_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    responder_handle: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 수락할 때 적은 아이디
    status: Mapped[str] = mapped_column(String(12), default="PENDING", nullable=False)  # INSTA_STATUSES
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
