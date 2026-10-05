"""매칭 정지 (2026-10-05)

- users.match_suspended: 관리자가 켜는 "매칭 정지". 켜져 있으면 서로 LIKE해도 매칭이 숨김(HIDDEN)으로 생긴다.
- users.match_suspended_at: 정지한 시각 (관리자 화면 정렬용)
matches.status에 HIDDEN 값이 새로 생기지만, 문자열 칸이라 테이블은 바꿀 필요가 없다.

Revision ID: 0017_match_suspension
Revises: 0016_membership
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_match_suspension"
down_revision: Union[str, None] = "0016_membership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("match_suspended", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("match_suspended_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("match_suspended_at")
        batch_op.drop_column("match_suspended")
