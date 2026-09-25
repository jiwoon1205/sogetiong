import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.matching import REPORT_REASONS


class TargetRequest(BaseModel):
    """LIKE / PASS / 차단 대상. 내부 user_id 대신 공개 profile_id를 쓴다."""

    profile_id: uuid.UUID


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("빈 메시지는 보낼 수 없습니다.")
        return value


class ReportRequest(BaseModel):
    profile_id: uuid.UUID
    reason: Literal[REPORT_REASONS]  # type: ignore[valid-type]
    description: str | None = Field(default=None, max_length=1000)
    match_id: uuid.UUID | None = None


class NotificationUpdateRequest(BaseModel):
    read: bool = True
