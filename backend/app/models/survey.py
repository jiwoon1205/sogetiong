import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk
from app.core.time import utcnow


class AppSetting(Base):
    """관리자 화면에서 켜고 끄는 서비스 설정 (2026-10-05).

    서버 .env와 달리 서버를 다시 켜지 않아도 바로 바뀐다.
    지금은 "survey_open"(설문 받는 중인지) 하나만 쓴다.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SurveyResponse(Base):
    """사용자 설문 응답 (2026-10-05 정식 오픈 전 설문). 계정 하나당 설문 하나에 한 번만 (user_id + survey_key 고유)."""

    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("user_id", "survey_key", name="uq_survey_responses_user_survey"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    survey_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # 1번: 외모 평가 방식 (survey_service.APPEARANCE_CHOICES 중 하나)
    appearance_choice: Mapped[str] = mapped_column(String(30), nullable=False)
    # 2번(기준 변경)·5번(기타)을 골랐을 때 적은 내용
    appearance_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 유료 시스템 만족도 1(매우 불만족) ~ 5(매우 만족)
    payment_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 기타 개선점·원하는 점 (선택)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
