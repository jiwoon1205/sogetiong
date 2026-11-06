"""탈퇴 사유 (2026-11-07)

- users.deleted_reason: 탈퇴할 때 사용자가 적은 사유 (선택, 최대 500자). 관리자만 본다.

Revision ID: 0031_withdrawal_reason
Revises: 0030_female_free_gender_lock
Create Date: 2026-11-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_withdrawal_reason"
down_revision: Union[str, None] = "0030_female_free_gender_lock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("deleted_reason")
