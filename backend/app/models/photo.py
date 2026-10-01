import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk, updated_at

PHOTO_STATUSES = ("PENDING", "IN_REVIEW", "APPROVED", "REJECTED", "SUPERSEDED")
# 외모 등급 (상/중/하). 관리자가 평가할 때 직접 고르고, 추천 순서에만 쓴다.
# ⚠️ 내부 데이터: 다른 사용자는 물론 본인에게도 절대 보내지 않는다.
APPEARANCE_TIERS = ("HIGH", "MID", "LOW")


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
    # 검수할 때 쓴 내부 메모 (운영진 전용, 사용자에게 절대 안 보임). 승인·반려 모두 여기에 남는다
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 한 번에 제출한 사진 묶음 (최대 3장, 2026-09-30). 같은 묶음은 같은 submission_id를 가지고 함께 검수된다.
    # position 0 = 묶음의 대표 사진 (관리자 대기열·평가 기록은 대표 사진 기준)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 평가 후 7일(PHOTO_RESUBMIT_DAYS)이 안 지났는데 "바로 재검토"(계정당 평생 1번)를 써서 낸 사진인지
    free_rereview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    ) + (CheckConstraint("tier IS NULL OR tier IN ('HIGH', 'MID', 'LOW')", name="ck_eval_tier"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    photo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("user_photos.id"), nullable=False)
    overall_impression: Mapped[int] = mapped_column(Integer, nullable=False)  # 전체적인 인상
    style: Mapped[int] = mapped_column(Integer, nullable=False)  # 스타일
    grooming: Mapped[int] = mapped_column(Integer, nullable=False)  # 자기관리
    photo_vibe: Mapped[int] = mapped_column(Integer, nullable=False)  # 사진 분위기
    evaluator_admin_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=False)
    evaluation_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # 관리자 전용 메모
    # 외모 등급 HIGH/MID/LOW (내부 전용, 공개 금지). 예전 평가는 비어 있을 수 있다 → 다시 평가해야 추천에 나온다
    tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = created_at()

    def scores(self) -> dict[str, int]:
        return {
            "overall_impression": self.overall_impression,
            "style": self.style,
            "grooming": self.grooming,
            "photo_vibe": self.photo_vibe,
        }
