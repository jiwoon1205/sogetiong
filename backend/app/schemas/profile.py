import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileUpdateRequest(BaseModel):
    """PATCH /me/profile — 보낸 항목만 바뀐다. 성별·생년월일·캠퍼스는 가입 후 바꿀 수 없다."""

    nickname: str | None = Field(default=None, min_length=2, max_length=20)
    department_id: uuid.UUID | None = None
    clear_department: bool = False
    show_department: bool | None = None
    mbti: str | None = Field(default=None, pattern=r"^[EIei][NSns][TFtf][JPjp]$")
    bio: str | None = Field(default=None, max_length=500)
    ideal_type: str | None = Field(default=None, max_length=300)
    interests: list[str] | None = Field(default=None, max_length=10)

    @field_validator("mbti")
    @classmethod
    def upper_mbti(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class PreferencesRequest(BaseModel):
    """PUT /me/preferences — 매칭 조건 전체를 한 번에 저장한다."""

    preferred_gender: Literal["MALE", "FEMALE", "ANY"]
    min_age: int = Field(ge=19, le=60)
    max_age: int = Field(ge=19, le=60)
    campus_mode: Literal["MY", "ALL", "SELECTED"] = "ALL"
    campus_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    excluded_department_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    preferred_department_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def check(self):
        if self.min_age > self.max_age:
            raise ValueError("최소 나이가 최대 나이보다 클 수 없습니다.")
        if self.campus_mode == "SELECTED" and not self.campus_ids:
            raise ValueError("캠퍼스를 하나 이상 선택해주세요.")
        if set(self.excluded_department_ids) & set(self.preferred_department_ids):
            raise ValueError("같은 학과를 제외와 선호에 동시에 넣을 수 없습니다.")
        return self
