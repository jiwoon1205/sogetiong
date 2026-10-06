"""무료 체험 플랜 + 이용권 구매 시 사진 바로 재검토 1회 (2026-10-06)

- users.trial_likes_used: 체험으로 보낸 LIKE 수 (평생). 기존 회원은 0 → 유료 시작 때 모두 체험 LIKE 3개
- users.rereview_granted_at: 이용권·VIP를 산 시각 ("바로 재검토 1회" 혜택)
- likes.is_trial: 체험 LIKE 표시 (하루 한도에서 빼고 셈)
- user_photos.purchase_rereview: 구매 혜택으로 낸 사진

Revision ID: 0021_free_trial
Revises: 0020_announcement_seen
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_free_trial"
down_revision: Union[str, None] = "0020_announcement_seen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trial_likes_used", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rereview_granted_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("likes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("user_photos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purchase_rereview", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("user_photos", schema=None) as batch_op:
        batch_op.drop_column("purchase_rereview")
    with op.batch_alter_table("likes", schema=None) as batch_op:
        batch_op.drop_column("is_trial")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("rereview_granted_at")
        batch_op.drop_column("trial_likes_used")
