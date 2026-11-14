"""대화방 사진 보내기 · 인스타 아이디 교환 (2026-11-14)

- chat_photos: 대화방에서 보낸 사진 (1회 보기 / 대화에 보관). 관리자 확인용으로 90일 보관
- insta_shares: 인스타 아이디 교환 요청·수락·거절
- 신고 사유 FAKE_INSTA_ID(가짜·오타 인스타 아이디)는 글자 칸이라 DB 변경 없음

Revision ID: 0038_chat_photo_insta
Revises: 0037_like_events
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038_chat_photo_insta"
down_revision: Union[str, None] = "0037_like_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_chat_photos_match_id", "chat_photos", ["match_id"])
    op.create_index("ix_chat_photos_sender_user_id", "chat_photos", ["sender_user_id"])
    op.create_table(
        "insta_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("request_message_id", sa.Uuid(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("requester_handle", sa.String(length=30), nullable=False),
        sa.Column("responder_user_id", sa.Uuid(), nullable=False),
        sa.Column("responder_handle", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["request_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["responder_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_message_id"),
    )
    op.create_index("ix_insta_shares_match_id", "insta_shares", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_insta_shares_match_id", table_name="insta_shares")
    op.drop_table("insta_shares")
    op.drop_index("ix_chat_photos_sender_user_id", table_name="chat_photos")
    op.drop_index("ix_chat_photos_match_id", table_name="chat_photos")
    op.drop_table("chat_photos")
