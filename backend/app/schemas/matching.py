from pydantic import BaseModel


class LikeRequest(BaseModel):
    to_user_id: str


class MatchResponse(BaseModel):
    liked: bool
    matched: bool
    match_id: str | None = None
    chat_room_id: str | None = None


class SendMessageRequest(BaseModel):
    body: str
