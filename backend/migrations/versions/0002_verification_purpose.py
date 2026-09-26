"""인증번호에 용도(purpose) 추가: 가입(SIGNUP) / 비밀번호 재설정(PASSWORD_RESET)

Revision ID: 0002_verification_purpose
Revises: fa97be8fe3de
Create Date: 2026-09-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_verification_purpose"
down_revision: Union[str, None] = "fa97be8fe3de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 인증번호는 모두 가입용이므로 기본값 SIGNUP으로 채운다
    with op.batch_alter_table("verification_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purpose", sa.String(length=20), server_default="SIGNUP", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("verification_tokens", schema=None) as batch_op:
        batch_op.drop_column("purpose")
