import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


# ---------- Layer 2: 매칭 조건 (다른 사용자에게 절대 공개하지 않음) ----------

class MatchingPreference(Base):
    __tablename__ = "matching_preferences"
    __table_args__ = (CheckConstraint("min_age <= max_age", name="ck_pref_age_range"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    # 원하는 성별은 여기 없다 → PrivateProfile.preferred_gender (가입 때 정하고 본인은 못 바꿈)
    # 나이 범위. 비어 있으면(None) 그쪽은 제한 없음 → 둘 다 비어 있으면 "나이 상관없음" (2026-09-30)
    # max_age가 비어 있는 경우 = 가로 바 오른쪽 끝("35세 이상")까지 고른 경우도 포함
    min_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campus_mode: Mapped[str] = mapped_column(String(20), default="ALL", nullable=False)  # MY / ALL / SELECTED
    # 같은 과 제외: 둘 중 한 명이라도 켰고 학과가 같으면 서로 추천되지 않는다
    exclude_same_department: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    # 매칭 조건 변경 횟수 제한(하루 3번)용: 24시간 창이 시작된 시각과 그 안에서 바꾼 횟수
    change_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changes_in_window: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class PreferredCampus(Base):
    """campus_mode = SELECTED 일 때 고른 캠퍼스들."""

    __tablename__ = "preferred_campuses"
    __table_args__ = (UniqueConstraint("user_id", "campus_id", name="uq_pref_campus"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    campus_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campuses.id"), nullable=False)
    created_at: Mapped[datetime] = created_at()


class ExcludedDepartment(Base):
    """만나고 싶지 않은 학과 — Hard Filter (설계도 §15).

    베타에서는 쓰지 않는다 ("같은 과 제외" 스위치 하나만 사용). 나중에 다시 쓸 수 있게 테이블만 남겨둔다.
    """

    __tablename__ = "excluded_departments"
    __table_args__ = (UniqueConstraint("user_id", "department_id", name="uq_excluded_dept"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id"), nullable=False)
    created_at: Mapped[datetime] = created_at()


class PreferredDepartment(Base):
    """선호 학과 — 추천 순위에만 쓰는 Soft Preference (설계도 §16).

    베타에서는 쓰지 않는다. 나중에 다시 쓸 수 있게 테이블만 남겨둔다.
    """

    __tablename__ = "preferred_departments"
    __table_args__ = (UniqueConstraint("user_id", "department_id", name="uq_preferred_dept"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id"), nullable=False)
    created_at: Mapped[datetime] = created_at()


# ---------- LIKE / PASS / MATCH ----------

class Like(Base):
    """LIKE와 PASS를 한 테이블에 기록한다. action: LIKE / PASS (설계도 §21, §22)."""

    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id", name="uq_likes_from_to"),)

    id: Mapped[uuid.UUID] = pk()
    from_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    to_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Match(Base):
    """user_a_id < user_b_id 순서로 저장해 같은 쌍이 두 번 생기지 않게 한다.
    status: ACTIVE / UNMATCHED / BLOCKED / HIDDEN

    HIDDEN (2026-10-05): 둘 중 한 명이 "매칭 정지" 상태일 때 생긴 매칭. 두 사람 모두에게 보이지 않고
    (매칭 목록·끝난 대화·알림 어디에도 없음), 관리자가 "다시 보이게"를 누르면 ACTIVE가 된다."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id", name="uq_matches_user_pair"),)

    id: Mapped[uuid.UUID] = pk()
    user_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    user_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    def partner_of(self, user_id: uuid.UUID) -> uuid.UUID:
        return self.user_b_id if self.user_a_id == user_id else self.user_a_id

    def has_member(self, user_id: uuid.UUID) -> bool:
        return user_id in (self.user_a_id, self.user_b_id)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = pk()
    match_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("matches.id"), nullable=False, index=True)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="TEXT", nullable=False)
    created_at: Mapped[datetime] = created_at()


# ---------- 안전 ----------

class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_block_pair"),)

    id: Mapped[uuid.UUID] = pk()
    blocker_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    blocked_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = created_at()


REPORT_REASONS = (
    "SEXUAL_HARASSMENT",  # 성희롱
    "ABUSIVE_LANGUAGE",  # 욕설
    "THREAT",  # 협박
    "STALKING",  # 스토킹
    "OBSCENE_CONTENT",  # 음란물
    "IMPERSONATION",  # 사칭
    "MONEY_REQUEST",  # 금전 요구
    "PERSONAL_INFO_REQUEST",  # 개인정보 요구
    "SPAM",  # 스팸
    "OTHER",  # 기타
)


class Report(Base):
    """status: OPEN / IN_REVIEW / RESOLVED / DISMISSED"""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = pk()
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    reported_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    match_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("matches.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = created_at()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    """type: MATCH_CREATED / NEW_MESSAGE / REPORT_RESULT / ACCOUNT_STATUS / PHOTO_REVIEWED"""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
