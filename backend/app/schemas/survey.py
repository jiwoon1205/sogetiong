from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clean(text: str | None) -> str | None:
    """앞뒤 공백을 지우고, 비어 있으면 None."""
    if text is None:
        return None
    text = text.strip()
    return text or None


class SurveyAnswerRequest(BaseModel):
    """POST /me/survey (2026-11-22 찬반 투표: 찾는 관계 '대학교 친구' 없애기)

    - vote: AGREE(찬성, 없애자) / DISAGREE(반대, 남기자). 꼭 골라야 한다
    - comment: 하고 싶은 말 (선택)
    """

    vote: Literal["AGREE", "DISAGREE"]
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        return _clean(v)


class SurveyOpenRequest(BaseModel):
    """PUT /admin/survey/open"""

    open: bool
