"""앱(홈 화면 아이콘)으로 연 기록 (2026-11-24): users.app_opened_at, users.app_platform.

Revision ID: 0048_app_open
Revises: 0047_survey_vote
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048_app_open"
down_revision: Union[str, None] = "0047_survey_vote"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("app_opened_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("app_platform", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("app_platform")
        batch.drop_column("app_opened_at")
