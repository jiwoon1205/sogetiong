from pydantic import BaseModel, Field


class PhotoReviewRequest(BaseModel):
    decision: str = "APPROVED"
    overall_impression: int | None = Field(default=None, ge=1, le=10)
    style: int | None = Field(default=None, ge=1, le=10)
    grooming: int | None = Field(default=None, ge=1, le=10)
    photo_vibe: int | None = Field(default=None, ge=1, le=10)
    note: str | None = None