"""게시판·쪽지 요청 형식 (2026-11-22)."""

import uuid

from pydantic import BaseModel, Field


class BoardProfileCreate(BaseModel):
    nickname: str = Field(max_length=40)
    shown_score: str | None = None


class BoardProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=40)
    shown_score: str | None = None
    # shown_score를 바꾸려는 건지 (None = 공개 안 함 과 구분)
    change_score: bool = False


class PostCreate(BaseModel):
    board: str = "FREE"
    title: str = Field(max_length=200)
    body: str = Field(max_length=5000)


class CommentCreate(BaseModel):
    body: str = Field(max_length=2000)
    # 답글이면 답할 댓글 id (2026-11-22)
    reply_to_id: uuid.UUID | None = None


class BoardReportCreate(BaseModel):
    target_type: str
    target_id: uuid.UUID
    reason: str
    description: str | None = Field(default=None, max_length=1000)


class NoteOpen(BaseModel):
    board_profile_id: uuid.UUID
    body: str = Field(max_length=3000)
    post_id: uuid.UUID | None = None


class NoteSend(BaseModel):
    body: str = Field(max_length=3000)


class BoardBlock(BaseModel):
    board_profile_id: uuid.UUID


class BoardBan(BaseModel):
    days: int | None = Field(default=7, description="7 / 30 / None(영구)")
    reason: str = Field(min_length=1, max_length=300)


class BoardReportResolve(BaseModel):
    status: str = "RESOLVED"  # RESOLVED / DISMISSED
