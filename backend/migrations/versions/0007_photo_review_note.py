"""사진 검수 내부 메모

- user_photos.review_note: 검수할 때 쓴 내부 메모 (운영진 전용).
  예전에는 반려할 때 쓴 메모가 어디에도 저장되지 않았다.
  기존 승인 사진은 appearance_evaluations에 남아 있던 메모를 옮겨 온다.

Revision ID: 0007_photo_review_note
Revises: 0006_matching_tier
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_photo_review_note"
down_revision: Union[str, None] = "0006_matching_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_photos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))

    # 승인 사진은 평가 기록에 메모가 있었으니 가장 최근 것을 옮겨 온다
    op.execute(
        """
        UPDATE user_photos
        SET review_note = (
            SELECT ae.evaluation_note FROM appearance_evaluations ae
            WHERE ae.photo_id = user_photos.id AND ae.evaluation_note IS NOT NULL
            ORDER BY ae.created_at DESC LIMIT 1
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("user_photos", schema=None) as batch_op:
        batch_op.drop_column("review_note")
