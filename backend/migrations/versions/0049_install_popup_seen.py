"""앱 설치 안내 팝업을 본 시각 (2026-11-24): users.install_popup_seen_at.

Revision ID: 0049_install_popup_seen
Revises: 0048_app_open
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_install_popup_seen"
down_revision: Union[str, None] = "0048_app_open"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("install_popup_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("install_popup_seen_at")
