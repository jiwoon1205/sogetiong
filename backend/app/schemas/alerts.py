from pydantic import BaseModel, Field, field_validator

from app.services.push_service import is_allowed_endpoint

_B64URL = r"^[A-Za-z0-9_\-]+={0,2}$"


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=60, max_length=200, pattern=_B64URL)
    auth: str = Field(min_length=16, max_length=100, pattern=_B64URL)


class PushSubscribeRequest(BaseModel):
    """브라우저가 만들어 준 알림 주소 (PushSubscription.toJSON() 그대로)."""

    endpoint: str = Field(max_length=1000)
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def _known_push_service(cls, v: str) -> str:
        if not is_allowed_endpoint(v):
            raise ValueError("이 브라우저는 휴대폰 알림을 지원하지 않아요. 크롬(안드로이드)이나 사파리(아이폰)로 열어 주세요.")
        return v


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(max_length=1000)


class AlertSettingsRequest(BaseModel):
    email_notify: bool


class AnnouncementSeenRequest(BaseModel):
    key: str = Field(max_length=60)
