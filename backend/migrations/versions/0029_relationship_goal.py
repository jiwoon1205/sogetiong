"""내가 찾는 관계 (2026-10-24): public_profiles.relationship_goal

SERIOUS 진지한 연애 / FRIEND 대학교 친구 / CASUAL 캐주얼한 만남. 예전 회원은 비어 있음(NULL).

Revision ID: 0029_relationship_goal
Revises: 0028_repeat_likes
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_relationship_goal"
down_revision: Union[str, None] = "0028_repeat_likes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("relationship_goal", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.drop_column("relationship_goal")
