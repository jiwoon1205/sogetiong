"""가입비 직접 입금 (2026-10-03)

- payments 표: 결제 코드·금액·상태 (CREATED → REQUESTED → CONFIRMED / REJECTED / REFUNDED)
- users.is_beta_member: 베타 회원은 가입비 면제. 지금까지 가입한 사람은 모두 true.
- users.signup_paid_at: 가입비 입금이 확인된 시각

Revision ID: 0014_signup_payment
Revises: 0013_profile_face_height
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_signup_payment"
down_revision: Union[str, None] = "0013_profile_face_height"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_beta_member", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("signup_paid_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(12), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by_admin_id", sa.Uuid(), sa.ForeignKey("admin_users.id"), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("signup_paid_at")
        batch_op.drop_column("is_beta_member")
