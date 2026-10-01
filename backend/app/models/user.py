import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


class User(Base):
    """계정. status: PENDING / ACTIVE / SUSPENDED / BANNED / DELETED (설계도 §61).

    email_hash: 학교 이메일의 지문(HMAC). 탈퇴하면 email은 가짜 주소로 바뀌고 이 값만 남는다.
    같은 사람이 다시 가입했는지 알아보는 데만 쓴다 (정지된 사람 재가입 차단, 차단 기록 이어받기).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    university_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("universities.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 마지막 접속 (관리자 확인용). 로그인할 때, 그리고 사이트를 쓰는 동안 10분에 한 번씩 기록한다.
    # 세션은 로그아웃하면 지워지므로 여기에 따로 남긴다.
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 탈퇴할 때 지워지는 공개 프로필에서 닉네임·성별만 관리자용으로 남긴다 (2026-10-01, 마이그레이션 0012).
    # 이게 없으면 관리자 화면에서 닉네임 검색·성별 필터로 탈퇴한 사람을 찾을 수 없다.
    deleted_nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deleted_gender: Mapped[str | None] = mapped_column(String(10), nullable=True)

    public_profile = relationship("PublicProfile", back_populates="user", uselist=False)
    private_profile = relationship("PrivateProfile", back_populates="user", uselist=False)


class UserDailyVisit(Base):
    """하루 접속 기록 (2026-10-01). 한 사람이 하루(한국 시간)에 한 줄만 쌓인다.

    - 추천 순서의 "활동 점수": 최근 14일 중 며칠 접속했나
    - 관리자 대시보드의 "활성 사용자": 최근 7일 안에 접속한 사람 수
    """

    __tablename__ = "user_daily_visits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    visit_date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)


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
