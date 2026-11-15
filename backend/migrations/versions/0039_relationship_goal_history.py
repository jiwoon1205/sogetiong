"""찾는 관계 변경 기록 relationship_goal_changes (2026-11-15)

찾는 관계(진지한 연애 / 대학교 친구 / 캐주얼한 만남)를 고르거나 바꿀 때마다 한 줄 남긴다.
관리자가 "캐주얼한 만남을 한 번이라도 고른 적 있는지" 볼 수 있게 한다. 지우지 않는다.

예전 변경은 기록이 없다 → 배포 시점에 찾는 관계를 골라 둔 사람마다 지금 값을 한 줄(source=BACKFILL) 채운다.
시각은 마지막으로 고른 시각(relationship_goal_changed_at), 없으면 프로필 수정 시각.

Revision ID: 0039_relationship_goal_history
Revises: 0038_chat_photo_insta
Create Date: 2026-11-15
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_relationship_goal_history"
down_revision: Union[str, None] = "0038_chat_photo_insta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    table = op.create_table(
        "relationship_goal_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("old_goal", sa.String(20), nullable=True),
        sa.Column("new_goal", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="USER"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relationship_goal_changes_user_id", "relationship_goal_changes", ["user_id"])

    conn = op.get_bind()
    profiles = sa.table(
        "public_profiles",
        sa.column("user_id", sa.Uuid()),
        sa.column("relationship_goal", sa.String()),
        sa.column("relationship_goal_changed_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = conn.execute(
        sa.select(
            profiles.c.user_id,
            profiles.c.relationship_goal,
            sa.func.coalesce(profiles.c.relationship_goal_changed_at, profiles.c.updated_at),
        ).where(profiles.c.relationship_goal.isnot(None))
    ).fetchall()
    if rows:
        op.bulk_insert(
            table,
            [
                {"id": uuid.uuid4(), "user_id": uid, "old_goal": None, "new_goal": goal, "source": "BACKFILL", "created_at": at}
                for uid, goal, at in rows
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_relationship_goal_changes_user_id", table_name="relationship_goal_changes")
    op.drop_table("relationship_goal_changes")
