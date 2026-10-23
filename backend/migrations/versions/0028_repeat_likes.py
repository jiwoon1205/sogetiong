"""추천 알고리즘 재설계 (2026-10-24): 좋아요 쌓기

- likes.like_count: 같은 사람에게 좋아요를 보낸 횟수 (매칭이 안 되면 48시간 뒤 다시 보낼 수 있다)
- matches.by_repeat_likes: 좋아요 5번째로 생긴 매칭 (슈퍼 라이크와 같은 효과, 표시 문구만 다름)

Revision ID: 0028_repeat_likes
Revises: 0027_referral
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_repeat_likes"
down_revision: Union[str, None] = "0027_referral"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("likes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("like_count", sa.Integer(), nullable=False, server_default="1"))
    # 넘기기(PASS)만 한 행은 좋아요 0번 (예전에는 LIKE한 사람이 다시 나오지 않아서 LIKE→PASS로 바뀐 행은 없다)
    op.execute("UPDATE likes SET like_count = 0 WHERE action = 'PASS'")
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("by_repeat_likes", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_column("by_repeat_likes")
    with op.batch_alter_table("likes", schema=None) as batch_op:
        batch_op.drop_column("like_count")
