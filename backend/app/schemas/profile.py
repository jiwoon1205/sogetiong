import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileUpdateRequest(BaseModel):
    """PATCH /me/profile — 보낸 항목만 바뀐다.

    성별·생년월일·캠퍼스는 가입 후 바꿀 수 없다.
    학과는 처음 한 번만 고를 수 있다 (잘못 골랐으면 운영진에게 메일로 요청 → 관리자가 변경).
    학과를 처음 고를 때 캠퍼스·학과 공개 여부도 함께 직접 골라야 한다.
    """

    nickname: str | None = Field(default=None, min_length=2, max_length=20)
    department_id: uuid.UUID | None = None
    show_department: bool | None = None
    show_campus: bool | None = None
    mbti: str | None = Field(default=None, pattern=r"^[EIei][NSns][TFtf][JPjp]$")
    bio: str | None = Field(default=None, max_length=500)
    ideal_type: str | None = Field(default=None, max_length=300)
    interests: list[str] | None = Field(default=None, max_length=10)

    @field_validator("mbti")
    @classmethod
    def upper_mbti(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class PreferencesRequest(BaseModel):
    """PUT /me/preferences — 매칭 조건 전체를 한 번에 저장한다.

    원하는 성별은 여기서 바꿀 수 없다 (가입할 때 정함). 보내도 무시된다.
    """

    min_age: int = Field(ge=19, le=60)
    max_age: int = Field(ge=19, le=60)
    campus_mode: Literal["MY", "ALL", "SELECTED"] = "ALL"
    campus_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    exclude_same_department: bool = False

    @model_validator(mode="after")
    def check(self):
        if self.min_age > self.max_age:
            raise ValueError("최소 나이가 최대 나이보다 클 수 없습니다.")
        if self.campus_mode == "SELECTED" and not self.campus_ids:
            raise ValueError("캠퍼스를 하나 이상 선택해주세요.")
        return self
