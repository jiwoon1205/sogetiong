"""관리자가 주는 "오늘만" 추가 좋아요 (2026-10-10)

- users.bonus_likes: 추가 좋아요 개수
- users.bonus_likes_date: 그 좋아요를 쓸 수 있는 날 (한국 시간). 이 날이 지나면 저절로 무시된다

Revision ID: 0023_bonus_likes
Revises: 0022_match_reads
Create Date: 2026-10-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_bonus_likes"
down_revision: Union[str, None] = "0022_match_reads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bonus_likes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("bonus_likes_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("bonus_likes_date")
        batch_op.drop_column("bonus_likes")
