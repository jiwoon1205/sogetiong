from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _clean(text: str | None) -> str | None:
    """앞뒤 공백을 지우고, 비어 있으면 None."""
    if text is None:
        return None
    text = text.strip()
    return text or None


class SurveyAnswerRequest(BaseModel):
    """POST /me/survey"""

    appearance_choice: Literal["AI_ONLY", "AI_NEW_CRITERIA", "AI_PLUS_ADMIN", "ADMIN_ONLY", "OTHER"]
    appearance_comment: str | None = Field(default=None, max_length=500)
    payment_rating: int = Field(ge=1, le=5)
    payment_comment: str | None = Field(default=None, max_length=500)
    suggestion: str | None = Field(default=None, max_length=1000)

    @field_validator("appearance_comment", "payment_comment", "suggestion")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        return _clean(v)

    @model_validator(mode="after")
    def other_needs_comment(self):
        # "기타"를 고르면 어떤 방식인지 꼭 적어야 한다
        if self.appearance_choice == "OTHER" and not self.appearance_comment:
            raise ValueError("'기타'를 골랐다면 원하는 방식을 적어주세요.")
        return self


class SurveyOpenRequest(BaseModel):
    """PUT /admin/survey/open"""

    open: bool
