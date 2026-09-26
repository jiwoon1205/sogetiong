import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


class User(Base):
    """계정. status: PENDING / ACTIVE / SUSPENDED / BANNED / DELETED (설계도 §61)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    university_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("universities.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    public_profile = relationship("PublicProfile", back_populates="user", uselist=False)
    private_profile = relationship("PrivateProfile", back_populates="user", uselist=False)


class UserSession(Base):
    """로그인 세션. 브라우저 쿠키에는 원문, DB에는 해시만 저장한다."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = created_at()


class VerificationToken(Base):
    """이메일 인증번호.

    purpose=SIGNUP: 학교 이메일 인증 → 가입용 1회 티켓 발급
    purpose=PASSWORD_RESET: 비밀번호 재설정 코드
    용도가 다른 코드는 서로 쓸 수 없다.
    """

    __tablename__ = "verification_tokens"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), default="SIGNUP", server_default="SIGNUP", nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    ticket_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
