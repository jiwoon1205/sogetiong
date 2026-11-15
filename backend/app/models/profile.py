import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
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
    # 본인이 고른 얼굴상·키 (2026-10-02, 둘 다 선택사항). 걸러보기·추천 순서에는 쓰지 않는다.
    face_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # FACE_TYPES 중 하나
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 내가 찾는 관계 (2026-10-24): SERIOUS 진지한 연애 / FRIEND 대학교 친구 / CASUAL 캐주얼한 만남.
    # 카드에 보이기만 하고 추천·매칭에는 쓰지 않는다. None = 아직 안 고름 (예전 회원)
    relationship_goal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 찾는 관계를 마지막으로 고른·바꾼 시각 (2026-11-11, 0032). 이때부터 RELATIONSHIP_GOAL_CHANGE_DAYS일 동안 다시 못 바꿈
    relationship_goal_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    user = relationship("User", back_populates="public_profile")
    campus = relationship("Campus")
    department = relationship("Department")


class RelationshipGoalChange(Base):
    """찾는 관계를 고르거나 바꿀 때마다 한 줄 (2026-11-15, 마이그레이션 0039). 관리자 확인용 기록.

    지우지 않는다: 탈퇴해서 공개 프로필이 지워져도 남고, 재가입하면 새 계정으로 옮겨진다
    (auth_service.carry_over_account). → "캐주얼한 만남을 한 번이라도 고른 적 있는지" 관리자가 알 수 있다.
    source: USER(사용자가 직접 고름·바꿈) / BACKFILL(0039 배포 때 그 시점의 값을 한 줄로 채움. 그 전 변경 기록은 없음)
    """

    __tablename__ = "relationship_goal_changes"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    old_goal: Mapped[str | None] = mapped_column(String(20), nullable=True)  # None = 처음 고름
    new_goal: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="USER", nullable=False)
    created_at: Mapped[datetime] = created_at()


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
