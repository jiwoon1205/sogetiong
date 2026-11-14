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
    """사용자 설문 응답. 계정 하나당 설문 하나에 한 번만 (user_id + survey_key 고유).

    - 2026-10-05 정식 오픈 전 설문(survey_key "2026-10-launch"): appearance_*, payment_*, suggestion
    - 2026-11-14 개선점·바라는 기능 설문(survey_key "2026-11-feedback"): improvement, feature_request
      둘 다 비어 있으면 "건너뛰기"를 누른 사람
    """

    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("user_id", "survey_key", name="uq_survey_responses_user_survey"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    survey_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # (옛 설문) 1번: 외모 평가 방식. 새 설문에서는 비어 있음
    appearance_choice: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 2번(기준 변경)·5번(기타)을 골랐을 때 적은 내용
    appearance_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # (옛 설문) 유료 시스템 만족도 1(매우 불만족) ~ 5(매우 만족). 새 설문에서는 비어 있음
    payment_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 기타 개선점·원하는 점 (선택)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    # (새 설문 2026-11-14) 개선했으면 하는 점
    improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    # (새 설문 2026-11-14) 새로 추가됐으면 하는 기능
    feature_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
