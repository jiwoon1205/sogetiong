"""캠퍼스 공개 여부 + "같은 과 제외" + 매칭 조건 변경 횟수 제한

- public_profiles.show_campus: 캠퍼스를 다른 학생에게 보여줄지 (NULL = 아직 고르지 않음 → 숨김)
- matching_preferences.exclude_same_department: 같은 과 제외 스위치
- matching_preferences.change_window_started_at / changes_in_window: 하루 3번 변경 제한용

Revision ID: 0005_campus_department
Revises: 0004_chats_read_permission
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_campus_department"
down_revision: Union[str, None] = "0004_chats_read_permission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("show_campus", sa.Boolean(), nullable=True))

    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.add_column(sa.Column("exclude_same_department", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("change_window_started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("changes_in_window", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.drop_column("changes_in_window")
        batch_op.drop_column("change_window_started_at")
        batch_op.drop_column("exclude_same_department")

    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.drop_column("show_campus")
