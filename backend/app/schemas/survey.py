from pydantic import BaseModel, Field, field_validator, model_validator


def _clean(text: str | None) -> str | None:
    """앞뒤 공백을 지우고, 비어 있으면 None."""
    if text is None:
        return None
    text = text.strip()
    return text or None


class SurveyAnswerRequest(BaseModel):
    """POST /me/survey (2026-11-14 새 설문: 개선점·바라는 기능)

    - skip = True: "건너뛰기". 적은 글은 저장하지 않고 빈 응답으로 남긴다 (다시 안 뜸)
    - skip = False: 둘 중 하나 이상 적어야 한다
    """

    improvement: str | None = Field(default=None, max_length=1000)
    feature_request: str | None = Field(default=None, max_length=1000)
    skip: bool = False

    @field_validator("improvement", "feature_request")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        return _clean(v)

    @model_validator(mode="after")
    def needs_some_text(self):
        if self.skip:
            self.improvement = None
            self.feature_request = None
        elif not self.improvement and not self.feature_request:
            raise ValueError("둘 중 하나는 적어주세요. 쓸 말이 없으면 '건너뛰기'를 눌러주세요.")
        return self


class SurveyOpenRequest(BaseModel):
    """PUT /admin/survey/open"""

    open: bool
