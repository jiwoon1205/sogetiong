"""사진 여러 장(최대 3장) 제출 + "바로 재검토" 1회 (2026-09-30)

- user_photos.submission_id: 한 번에 제출한 사진 묶음. 같은 묶음은 함께 검수된다.
  예전 사진은 한 장이 한 묶음 → 자기 id를 그대로 넣는다.
- user_photos.position: 묶음 안 순서 (0 = 대표 사진)
- user_photos.free_rereview: 평가 후 30일 안에 "바로 재검토"(계정당 1번)로 낸 사진인지

Revision ID: 0009_photo_submission
Revises: 0008_age_range_optional
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_photo_submission"
down_revision: Union[str, None] = "0008_age_range_optional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_photos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("submission_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("free_rereview", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index("ix_user_photos_submission_id", ["submission_id"])

    # 예전 사진: 한 장 = 한 묶음
    op.execute("UPDATE user_photos SET submission_id = id WHERE submission_id IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("user_photos", schema=None) as batch_op:
        batch_op.drop_index("ix_user_photos_submission_id")
        batch_op.drop_column("free_rereview")
        batch_op.drop_column("position")
        batch_op.drop_column("submission_id")
