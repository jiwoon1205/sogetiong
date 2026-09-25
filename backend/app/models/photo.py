import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk, updated_at

PHOTO_STATUSES = ("PENDING", "IN_REVIEW", "APPROVED", "REJECTED", "SUPERSEDED")


class UserPhoto(Base):
    """원본 사진 메타데이터 (설계도 §7). 파일 자체는 private storage에 있다."""

    __tablename__ = "user_photos"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_status: Mapped[str] = mapped_column(String(30), default="UPLOADED", nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    uploaded_at: Mapped[datetime] = created_at()
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class AppearanceEvaluation(Base):
    """외적 특징 평가 4개 항목 (설계도 §4). 수정할 때마다 새 행을 추가해 이력을 남기고,
    사용자별 가장 최근 행이 현재 공개되는 점수다."""

    __tablename__ = "appearance_evaluations"
    __table_args__ = tuple(
        CheckConstraint(f"{col} BETWEEN 1 AND 10", name=f"ck_eval_{col}")
        for col in ("overall_impression", "style", "grooming", "photo_vibe")
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    photo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("user_photos.id"), nullable=False)
    overall_impression: Mapped[int] = mapped_column(Integer, nullable=False)  # 전체적인 인상
    style: Mapped[int] = mapped_column(Integer, nullable=False)  # 스타일
    grooming: Mapped[int] = mapped_column(Integer, nullable=False)  # 자기관리
    photo_vibe: Mapped[int] = mapped_column(Integer, nullable=False)  # 사진 분위기
    evaluator_admin_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=False)
    evaluation_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # 관리자 전용 메모
    created_at: Mapped[datetime] = created_at()

    def scores(self) -> dict[str, int]:
        return {
            "overall_impression": self.overall_impression,
            "style": self.style,
            "grooming": self.grooming,
            "photo_vibe": self.photo_vibe,
        }
