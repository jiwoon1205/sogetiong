"""이용권 (2026-10-04 구독제)

- users.member_until: 이용권(기본·VIP 포함)이 끝나는 시각
- users.member_days_banked: 아직 시작하지 않은 이용권 일수 (사진 검수 전에 낸 첫 이용권)
기존 데이터는 옮기지 않는다 (스위치가 꺼져 있어 실제 결제가 없음).

Revision ID: 0016_membership
Revises: 0015_user_vip_until
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_membership"
down_revision: Union[str, None] = "0015_user_vip_until"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("member_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("member_days_banked", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("member_days_banked")
        batch_op.drop_column("member_until")
