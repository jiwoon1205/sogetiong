import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


class AdminRole(Base):
    """SUPER_ADMIN / MODERATOR / PHOTO_REVIEWER (설계도 §29).
    permissions_json 예: ["photos:read", "photos:evaluate"]"""

    __tablename__ = "admin_roles"

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    permissions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = created_at()


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("admin_roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    # TODO(운영 전): TOTP 비밀키를 KMS 등으로 암호화해서 저장
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    role = relationship("AdminRole")


class AdminSession(Base):
    """관리자 세션. 2단계 인증(mfa_verified_at)이 끝나야 관리자 API를 쓸 수 있다."""

    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = pk()
    admin_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = created_at()


class AuditLog(Base):
    """관리자 행위 기록 (설계도 §31). 개인정보 원문은 metadata에 넣지 않는다."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = pk()
    admin_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = created_at()


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "SUPER_ADMIN": [
        "dashboard:read",
        "photos:read",
        "photos:evaluate",
        "users:read",
        "users:status",
        "users:private:read",
        # 학과 변경: 사용자는 학과를 바꿀 수 없고, 가입 메일로 요청하면 운영진이 확인 후 바꾼다.
        # 본인 확인에 가입 이메일을 봐야 하므로 개인정보 조회 권한이 있는 최고 관리자만.
        "users:department",
        # 성별·원하는 성별 변경: 학과와 같은 이유로 최고 관리자만 (가입 메일로 본인 확인)
        "users:gender",
        "reports:read",
        "reports:update",
        "chats:read",
        "audit:read",
    ],
    # chats:read = 모든 대화 열람 (열 때마다 감사 로그에 CHAT_VIEW로 기록)
    "MODERATOR": ["dashboard:read", "users:read", "users:status", "reports:read", "reports:update", "chats:read"],
    "PHOTO_REVIEWER": ["dashboard:read", "photos:read", "photos:evaluate"],
}

SUPER_ADMIN_ROLE = "SUPER_ADMIN"
# 코드에 정의된 모든 권한. 최고 관리자는 목록에 빠진 권한이 있어도 항상 전부 가진다.
ALL_PERMISSIONS: frozenset[str] = frozenset(p for perms in ROLE_PERMISSIONS.values() for p in perms)
