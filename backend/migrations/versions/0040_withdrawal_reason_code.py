"""탈퇴 사유 고르기 (2026-11-16)

- users.deleted_reason_code: 탈퇴할 때 목록에서 고른 사유 (DATING, PRICE, NO_MATCH, NO_ONE, CHAT, BAD_USER, BREAK, OTHER).
  기타(OTHER)면 users.deleted_reason에 적은 글이 들어간다. 예전 탈퇴자는 비어 있음(글만 있음).

Revision ID: 0040_withdrawal_reason_code
Revises: 0039_relationship_goal_history
Create Date: 2026-11-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_withdrawal_reason_code"
down_revision: Union[str, None] = "0039_relationship_goal_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_reason_code", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("deleted_reason_code")
