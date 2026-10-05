"""한 번만 보여주는 공지 팝업 (2026-10-05)

- users.announcement_seen: 마지막으로 "확인"을 누른 공지 이름 (예: push-alerts-2026-10)

Revision ID: 0020_announcement_seen
Revises: 0019_push_notifications
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_announcement_seen"
down_revision: Union[str, None] = "0019_push_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("announcement_seen", sa.String(length=60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("announcement_seen")
