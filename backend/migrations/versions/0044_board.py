"""자유게시판 · 쪽지 (2026-11-22)

board_profiles(게시판 전용 프로필) · board_posts(자유·연애·캐주얼) · board_comments · board_reports · note_rooms · note_messages.
기존 표는 바꾸지 않는다.

Revision ID: 0044_board
Revises: 0043_watch_origin
Create Date: 2026-11-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044_board"
down_revision: Union[str, None] = "0043_watch_origin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "board_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nickname", sa.String(20), nullable=False),
        sa.Column("nickname_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avatar_key", sa.String(300), nullable=True),
        sa.Column("shown_score", sa.String(30), nullable=True),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_reason", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("nickname"),
    )
    op.create_table(
        "board_posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("board", sa.String(10), nullable=False, server_default="FREE"),
        sa.Column("title", sa.String(40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_admin_id", sa.Uuid(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_posts_author_user_id", "board_posts", ["author_user_id"])
    op.create_index("ix_board_posts_created_at", "board_posts", ["created_at"])
    op.create_index("ix_board_posts_board", "board_posts", ["board"])
    op.create_table(
        "board_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("board_posts.id"), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_admin_id", sa.Uuid(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_board_comments_post_id", "board_comments", ["post_id"])
    op.create_index("ix_board_comments_author_user_id", "board_comments", ["author_user_id"])
    op.create_table(
        "board_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reported_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reporter_user_id", "target_type", "target_id", name="uq_board_report_once"),
    )
    op.create_index("ix_board_reports_reporter_user_id", "board_reports", ["reporter_user_id"])
    op.create_index("ix_board_reports_reported_user_id", "board_reports", ["reported_user_id"])
    op.create_index("ix_board_reports_target_id", "board_reports", ["target_id"])
    op.create_index("ix_board_reports_status", "board_reports", ["status"])
    op.create_table(
        "note_rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("starter_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receiver_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("board_posts.id"), nullable=True),
        sa.Column("paid_with", sa.String(12), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("starter_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receiver_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_note_rooms_starter_user_id", "note_rooms", ["starter_user_id"])
    op.create_index("ix_note_rooms_receiver_user_id", "note_rooms", ["receiver_user_id"])
    op.create_table(
        "note_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("note_rooms.id"), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_note_messages_room_id", "note_messages", ["room_id"])


def downgrade() -> None:
    op.drop_index("ix_note_messages_room_id", table_name="note_messages")
    op.drop_table("note_messages")
    op.drop_index("ix_note_rooms_receiver_user_id", table_name="note_rooms")
    op.drop_index("ix_note_rooms_starter_user_id", table_name="note_rooms")
    op.drop_table("note_rooms")
    for ix in ("status", "target_id", "reported_user_id", "reporter_user_id"):
        op.drop_index(f"ix_board_reports_{ix}", table_name="board_reports")
    op.drop_table("board_reports")
    op.drop_index("ix_board_comments_author_user_id", table_name="board_comments")
    op.drop_index("ix_board_comments_post_id", table_name="board_comments")
    op.drop_table("board_comments")
    op.drop_index("ix_board_posts_board", table_name="board_posts")
    op.drop_index("ix_board_posts_created_at", table_name="board_posts")
    op.drop_index("ix_board_posts_author_user_id", table_name="board_posts")
    op.drop_table("board_posts")
    op.drop_table("board_profiles")
