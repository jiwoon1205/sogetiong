"""이탈 막기 (2026-11-16): 매칭 확률 높이기 팝업·휴면 좋아요 알림 기록

- users.match_tip_seen_at: 매칭 확률 높이기 팝업을 닫은 시각 (한 번만 보여준다)
- users.winback_sent_at: 휴면 좋아요 알림을 마지막으로 보낸 시각 (3일에 최대 1번)

Revision ID: 0041_engagement
Revises: 0040_withdrawal_reason_code
Create Date: 2026-11-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_engagement"
down_revision: Union[str, None] = "0040_withdrawal_reason_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("match_tip_seen_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("winback_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("winback_sent_at")
        batch_op.drop_column("match_tip_seen_at")
