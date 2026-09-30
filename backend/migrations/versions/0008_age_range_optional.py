"""매칭 조건 나이 범위를 비워 둘 수 있게 (가로 바 + "나이 상관없음", 2026-09-30)

- matching_preferences.min_age / max_age: 비어 있어도 됨(NULL)
  - 둘 다 NULL = "나이 상관없음"
  - max_age NULL = 가로 바 오른쪽 끝 "35세 이상" (위쪽 제한 없음)
- 기존 값 정리 (화면의 가로 바에 보이는 값과 실제 조건이 같도록):
  - max_age가 35 이상 → NULL ("35세 이상")
  - min_age가 35보다 크면 → 35
- CHECK(min_age <= max_age)는 그대로 둔다. 한쪽이 NULL이면 DB가 통과시킨다.

Revision ID: 0008_age_range_optional
Revises: 0007_photo_review_note
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_age_range_optional"
# 같은 날 만든 0007_photo_review_note 다음 순서 (둘 다 0006 뒤에 붙어 있어서 서버가 켜지지 않았음 → 한 줄로 이음)
down_revision: Union[str, None] = "0007_photo_review_note"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AGE_CAP = 35  # app/core/config.py 의 preference_age_cap 기본값과 같게


def upgrade() -> None:
    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.alter_column("min_age", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("max_age", existing_type=sa.Integer(), nullable=True)

    op.execute(f"UPDATE matching_preferences SET max_age = NULL WHERE max_age >= {AGE_CAP}")
    op.execute(f"UPDATE matching_preferences SET min_age = {AGE_CAP} WHERE min_age > {AGE_CAP}")


def downgrade() -> None:
    # 비어 있는 값을 예전처럼 숫자로 채운다: 최소 19, 최대 60 (예전 입력 칸의 범위)
    op.execute("UPDATE matching_preferences SET min_age = 19 WHERE min_age IS NULL")
    op.execute("UPDATE matching_preferences SET max_age = 60 WHERE max_age IS NULL")
    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.alter_column("min_age", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("max_age", existing_type=sa.Integer(), nullable=False)
