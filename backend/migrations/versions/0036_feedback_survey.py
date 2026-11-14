"""개선점·바라는 기능 설문 (2026-11-14)

- 옛 설문(외모 평가 방식·유료 만족도)을 내리고, 글로 답하는 새 설문으로 바꾼다.
- survey_responses.improvement / feature_request: 새 질문 2개의 답 (비어 있어도 됨)
- appearance_choice / payment_rating: 새 설문에는 없는 질문이라 비어 있어도 되게 바꾼다 (옛 응답은 그대로 남음)

Revision ID: 0036_feedback_survey
Revises: 0035_rec_quota_slots
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036_feedback_survey"
down_revision: Union[str, None] = "0035_rec_quota_slots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("survey_responses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("improvement", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("feature_request", sa.Text(), nullable=True))
        batch_op.alter_column("appearance_choice", existing_type=sa.String(length=30), nullable=True)
        batch_op.alter_column("payment_rating", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # 새 설문 응답(옛 질문이 비어 있는 줄)은 되돌릴 수 없으니 지운다
    op.execute("DELETE FROM survey_responses WHERE appearance_choice IS NULL OR payment_rating IS NULL")
    with op.batch_alter_table("survey_responses", schema=None) as batch_op:
        batch_op.alter_column("payment_rating", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("appearance_choice", existing_type=sa.String(length=30), nullable=False)
        batch_op.drop_column("feature_request")
        batch_op.drop_column("improvement")
