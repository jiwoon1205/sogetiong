from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    bio: str | None = None
    mbti: str | None = None
    interests: list[str] | None = None


class PublicProfileResponse(BaseModel):
    id: str
    nickname: str
    campus_id: str | None = None
    age: int | None = None
    gender: str | None = None
    mbti: str | None = None
    bio: str | None = None
    appearance_summary_json: dict | None = None
    profile_status: str = "ACTIVE"

    model_config = {"from_attributes": True}
