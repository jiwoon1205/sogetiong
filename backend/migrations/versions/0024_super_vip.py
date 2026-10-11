"""슈퍼 VIP (2026-10-12): 관리자가 지정. 영구 무료 VIP + 상대의 나이·캠퍼스 조건과 무관하게 추천에 나온다

Revision ID: 0024_super_vip
Revises: 0023_bonus_likes
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_super_vip"
down_revision: Union[str, None] = "0023_bonus_likes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("super_vip", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("super_vip")
