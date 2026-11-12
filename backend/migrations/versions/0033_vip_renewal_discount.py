"""VIP 재구매 할인 (2026-11-12)

- payments.renewal_discount: VIP 재구매 할인 금액 (0이면 할인 없음).
  VIP를 산 적 있는 사람이 VIP가 끝나기 3일 전 ~ 끝난 뒤 3일 안에 다시 사면 1,000원 할인.
  관리자 결제 확인 화면에 "재구매"로 보인다. 기존 결제는 모두 0.

Revision ID: 0033_vip_renewal_discount
Revises: 0032_relationship_goal_cooldown
Create Date: 2026-11-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_vip_renewal_discount"
down_revision: Union[str, None] = "0032_relationship_goal_cooldown"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("renewal_discount", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_column("renewal_discount")
