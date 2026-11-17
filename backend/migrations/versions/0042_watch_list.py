"""감시 대상 watch_events · watch_targets (2026-11-17, 관리자 전용)

캐주얼한 만남을 고르지 않은 사람이 캐주얼한 만남을 고른 사람에게 좋아요·슈퍼 라이크를 보내거나
보내려다 막히면 watch_events에 한 줄, 그 사람을 watch_targets에 올린다. 사용자에게는 보이지 않는다.
예전 일은 채우지 않는다 (지금부터 기록).

Revision ID: 0042_watch_list
Revises: 0041_engagement
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_watch_list"
down_revision: Union[str, None] = "0041_engagement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_goal", sa.String(20), nullable=True),
        sa.Column("is_super", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watch_events_user_id", "watch_events", ["user_id"])
    op.create_index("ix_watch_events_created_at", "watch_events", ["created_at"])
    op.create_table(
        "watch_targets",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="WATCHING"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_watch_targets_last_at", "watch_targets", ["last_at"])


def downgrade() -> None:
    op.drop_index("ix_watch_targets_last_at", table_name="watch_targets")
    op.drop_table("watch_targets")
    op.drop_index("ix_watch_events_created_at", table_name="watch_events")
    op.drop_index("ix_watch_events_user_id", table_name="watch_events")
    op.drop_table("watch_events")
