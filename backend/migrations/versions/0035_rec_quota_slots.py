"""좋아요 3·4번 쌓인 사람 노출 제한 (2026-11-13)

- rec_quota_slots: 이용권 기간마다 "좋아요를 3번 보낸 사람"·"4번 보낸 사람" 중 추천에 나올 수 있는 자리를 받은 사람.
  (보는 사람, 추천에 나온 사람, 3 또는 4) 한 줄씩. 이용권·VIP 입금이 확인되면 그 사람 줄을 모두 지운다.
- 새 표만 만든다. 기존 데이터는 바꾸지 않는다 → 배포 직후에는 모두 빈 자리에서 시작.

Revision ID: 0035_rec_quota_slots
Revises: 0034_signup_super_like_gift
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035_rec_quota_slots"
down_revision: Union[str, None] = "0034_signup_super_like_gift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rec_quota_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_user_id", "level", name="uq_rec_quota_slot"),
    )
    with op.batch_alter_table("rec_quota_slots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rec_quota_slots_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("rec_quota_slots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rec_quota_slots_user_id"))
    op.drop_table("rec_quota_slots")
