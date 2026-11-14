import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


class InstaHandleRequest(BaseModel):
    """인스타 아이디 교환 요청·수락 (2026-11-14).
    agree: "가짜·오타 아이디는 영구정지돼요"에 동의했는지. 동의하지 않으면 보낼 수 없다."""

    handle: str = Field(min_length=1, max_length=40)
    agree: bool = False

    @model_validator(mode="after")
    def must_agree(self):
        if not self.agree:
            raise ValueError("가짜·오타 아이디는 영구정지된다는 안내에 동의해야 보낼 수 있어요.")
        return self


class ReportRequest(BaseModel):
    """신고 대상은 둘 중 하나로 정한다.
    - match_id: 대화방 상대 (상대가 탈퇴해서 프로필이 없어도, 대화가 끝났어도 신고 가능)
    - profile_id: 추천 카드 등에서 본 프로필
    """

    profile_id: uuid.UUID | None = None
    reason: Literal[REPORT_REASONS]  # type: ignore[valid-type]
    description: str | None = Field(default=None, max_length=1000)
    match_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def needs_target(self):
        if self.profile_id is None and self.match_id is None:
            raise ValueError("신고할 상대를 알 수 없습니다.")
        return self


class NotificationUpdateRequest(BaseModel):
    read: bool = True
