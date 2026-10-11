"""슈퍼 라이크 (2026-10-12)

- users.super_likes: 남은 슈퍼 라이크 개수
- likes.is_super: 슈퍼 라이크로 보낸 LIKE (하루 LIKE 한도에서 빼고 셈)
- matches.super_like_by: 슈퍼 라이크로 생긴 매칭이면 보낸 사람 (답장 전 메시지 1개 제한)
- payments.quantity: 슈퍼 라이크 개수 (이용권·VIP는 1)

Revision ID: 0025_super_like
Revises: 0024_super_vip
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_super_like"
down_revision: Union[str, None] = "0024_super_vip"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("super_likes", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("likes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_super", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("super_like_by", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key("fk_matches_super_like_by", "users", ["super_like_by"], ["id"])
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_column("quantity")
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_constraint("fk_matches_super_like_by", type_="foreignkey")
        batch_op.drop_column("super_like_by")
    with op.batch_alter_table("likes", schema=None) as batch_op:
        batch_op.drop_column("is_super")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("super_likes")
