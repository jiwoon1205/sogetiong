"""친구 초대 이벤트 (2026-10-24)

- users.referral_code: 내 초대 링크 코드 (무작위 6글자, 처음 볼 때 만든다)
- users.referred_by_id: 나를 초대한 사람 (이벤트 기간에 초대 링크로 가입한 경우)
- users.referral_rewarded_at: 내 첫 사진이 승인돼서 초대한 사람에게 슈퍼 라이크를 준 시각 (한 번만)

Revision ID: 0027_referral
Revises: 0026_remove_match_suspension
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_referral"
down_revision: Union[str, None] = "0026_remove_match_suspension"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("referral_code", sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column("referred_by_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("referral_rewarded_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_users_referral_code", ["referral_code"], unique=True)
        batch_op.create_index("ix_users_referred_by_id", ["referred_by_id"], unique=False)
        batch_op.create_foreign_key("fk_users_referred_by_id", "users", ["referred_by_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_users_referred_by_id", type_="foreignkey")
        batch_op.drop_index("ix_users_referred_by_id")
        batch_op.drop_index("ix_users_referral_code")
        batch_op.drop_column("referral_rewarded_at")
        batch_op.drop_column("referred_by_id")
        batch_op.drop_column("referral_code")
