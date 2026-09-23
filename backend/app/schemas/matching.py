from pydantic import BaseModel


class LikeRequest(BaseModel):
    to_user_id: str


class MatchResponse(BaseModel):
    liked: bool
    matched: bool


class SendMessageRequest(BaseModel):
    body: str
