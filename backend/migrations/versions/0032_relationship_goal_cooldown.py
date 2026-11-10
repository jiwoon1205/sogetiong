"""찾는 관계 변경 쿨타임 (2026-11-11)

- public_profiles.relationship_goal_changed_at: 찾는 관계를 마지막으로 고른·바꾼 시각.
  이때부터 RELATIONSHIP_GOAL_CHANGE_DAYS일(기본 3일) 동안 다시 바꿀 수 없다.
  기존 회원은 비어 있음 → 지금 바로 한 번은 바꿀 수 있다.

Revision ID: 0032_relationship_goal_cooldown
Revises: 0031_withdrawal_reason
Create Date: 2026-11-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_relationship_goal_cooldown"
down_revision: Union[str, None] = "0031_withdrawal_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("relationship_goal_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.drop_column("relationship_goal_changed_at")
