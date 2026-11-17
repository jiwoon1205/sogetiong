"""감시 대상이 어떻게 올라왔는지 watch_targets.origin (2026-11-17)

LIKE = 캐주얼에게 좋아요를 보내서 자동으로 / MATCH_IMPORT = 예전 캐주얼 매칭 파일로 한꺼번에 (deploy/watch_import.py)

Revision ID: 0043_watch_origin
Revises: 0042_watch_list
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_watch_origin"
down_revision: Union[str, None] = "0042_watch_list"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("watch_targets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("origin", sa.String(20), nullable=False, server_default="LIKE"))


def downgrade() -> None:
    with op.batch_alter_table("watch_targets", schema=None) as batch_op:
        batch_op.drop_column("origin")
