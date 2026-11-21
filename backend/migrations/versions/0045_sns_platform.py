"""SNS 아이디 교환: 인스타 + 카톡 (2026-11-22). insta_shares에 platform 칸 추가 (예전 요청은 INSTAGRAM).

Revision ID: 0045_sns_platform
Revises: 0044_board
Create Date: 2026-11-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_sns_platform"
down_revision: Union[str, None] = "0044_board"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("insta_shares") as batch:
        batch.add_column(sa.Column("platform", sa.String(10), nullable=False, server_default="INSTAGRAM"))


def downgrade() -> None:
    with op.batch_alter_table("insta_shares") as batch:
        batch.drop_column("platform")
