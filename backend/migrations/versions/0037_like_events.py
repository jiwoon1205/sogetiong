"""좋아요 기록 표 like_events (2026-11-14)

좋아요를 한 번 보낼 때마다 한 줄 남긴다 (통계용: 날짜별 남녀 좋아요 수).
likes 표는 두 사람 사이에 한 줄만 두고 다시 보낼 때마다 새로 만들어서 날짜별 횟수를 알 수 없었다.
예전 좋아요는 채우지 않는다 (정확한 시각이 남아 있지 않음). 과거는 export_stats.py가 어림값을 따로 낸다.

Revision ID: 0037_like_events
Revises: 0036_feedback_survey
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_like_events"
down_revision: Union[str, None] = "0036_feedback_survey"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "like_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("like_no", sa.Integer(), nullable=False),
        sa.Column("is_trial", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_super", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_like_events_from_user_id", "like_events", ["from_user_id"])
    op.create_index("ix_like_events_created_at", "like_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_like_events_created_at", table_name="like_events")
    op.drop_index("ix_like_events_from_user_id", table_name="like_events")
    op.drop_table("like_events")
