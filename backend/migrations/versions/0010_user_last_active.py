"""사용자 마지막 접속 시각 (관리자 화면용, 2026-10-01)

- users.last_active_at: 로그인할 때, 그리고 사이트를 쓰는 동안 10분에 한 번 기록한다.
- 기존 사용자는 남아 있는 로그인 세션의 마지막 사용 시각으로 채운다
  (세션이 없으면 비워 두고, 다음 접속 때부터 기록된다).

Revision ID: 0010_user_last_active
Revises: 0009_photo_submission
Create Date: 2026-10-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_user_last_active"
down_revision: Union[str, None] = "0009_photo_submission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        "UPDATE users SET last_active_at = ("
        "SELECT MAX(s.last_used_at) FROM user_sessions s WHERE s.user_id = users.id"
        ") WHERE last_active_at IS NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_active_at")
