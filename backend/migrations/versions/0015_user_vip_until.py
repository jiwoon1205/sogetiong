"""VIP 이용권 (2026-10-03)

- users.vip_until: VIP가 끝나는 시각. 지금보다 뒤면 VIP. 비어 있으면 VIP 아님.
- VIP 결제는 payments 표에 kind='VIP'로 쌓인다 (새 표 없음).

Revision ID: 0015_user_vip_until
Revises: 0014_signup_payment
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_user_vip_until"
down_revision: Union[str, None] = "0014_signup_payment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("vip_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("vip_until")
