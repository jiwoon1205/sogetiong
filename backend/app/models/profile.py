import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


class PublicProfile(Base):
    """Layer 1 — 다른 사용자에게 보이는 정보 (설계도 §8).

    나이는 저장하지 않고 PrivateProfile.birth_date로 매번 계산한다.
    """

    __tablename__ = "public_profiles"

    id: Mapped[uuid.UUID] = pk()  # 외부에 노출되는 profile_id
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(40), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)  # MALE / FEMALE
    campus_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campuses.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("departments.id"), nullable=True)
    show_department: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 캠퍼스 공개 여부. None = 아직 고르지 않음(프로필 작성 단계에서 학과와 함께 직접 고른다) → 카드에서는 숨김
    show_campus: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mbti: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    ideal_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    user = relationship("User", back_populates="public_profile")
    campus = relationship("Campus")
    department = relationship("Department")


class PrivateProfile(Base):
    """Layer 3 — 관리자/내부 시스템만 접근 (설계도 §8)."""

    __tablename__ = "private_profiles"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    student_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 만나고 싶은 성별 (MALE / FEMALE / ANY). 가입할 때 정하고, 생년월일처럼 본인은 바꿀 수 없다.
    # 바꾸려면 운영진에게 메일로 요청 → 관리자가 변경 (PATCH /admin/users/{id}/gender)
    preferred_gender: Mapped[str] = mapped_column(String(10), nullable=False)
    verification_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    user = relationship("User", back_populates="private_profile")


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    created_at: Mapped[datetime] = created_at()


class UserInterest(Base):
    __tablename__ = "user_interests"
    __table_args__ = (UniqueConstraint("user_id", "interest_id", name="uq_user_interest"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    interest_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("interests.id"), nullable=False)
    created_at: Mapped[datetime] = created_at()

    interest = relationship("Interest")
