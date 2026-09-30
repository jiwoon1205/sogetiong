"""원하는 성별을 가입 정보로 이동 + 외모 등급(상/중/하)

- private_profiles.preferred_gender: 가입할 때 고르는 "원하는 성별" (본인은 변경 불가)
  기존 사용자는 matching_preferences에 있던 값을 옮기고, 없으면 ANY로 채운다.
- matching_preferences.preferred_gender: 삭제 (위로 옮겼으므로)
- appearance_evaluations.tier: 외모 등급 HIGH / MID / LOW (내부 전용, 공개 금지)
  기존 평가는 비워 둔다 → 관리자가 다시 등급을 정해야 추천에 나온다.

Revision ID: 0006_matching_tier
Revises: 0005_campus_department
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_matching_tier"
down_revision: Union[str, None] = "0005_campus_department"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 새 칸을 만들고 (기존 행 때문에 일단 비어 있어도 되게)
    with op.batch_alter_table("private_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("preferred_gender", sa.String(length=10), nullable=True))

    # 2) 매칭 조건에 있던 값을 옮기고, 없는 사람은 ANY
    op.execute(
        """
        UPDATE private_profiles
        SET preferred_gender = COALESCE(
            (SELECT mp.preferred_gender FROM matching_preferences mp WHERE mp.user_id = private_profiles.user_id),
            'ANY'
        )
        """
    )

    # 3) 이제 필수로 바꾸고, 매칭 조건 쪽 칸은 지운다
    with op.batch_alter_table("private_profiles", schema=None) as batch_op:
        batch_op.alter_column("preferred_gender", existing_type=sa.String(length=10), nullable=False)
    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.drop_column("preferred_gender")

    with op.batch_alter_table("appearance_evaluations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tier", sa.String(length=10), nullable=True))
        batch_op.create_check_constraint("ck_eval_tier", "tier IS NULL OR tier IN ('HIGH', 'MID', 'LOW')")


def downgrade() -> None:
    with op.batch_alter_table("appearance_evaluations", schema=None) as batch_op:
        batch_op.drop_constraint("ck_eval_tier", type_="check")
        batch_op.drop_column("tier")

    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.add_column(sa.Column("preferred_gender", sa.String(length=10), nullable=True))
    op.execute(
        """
        UPDATE matching_preferences
        SET preferred_gender = COALESCE(
            (SELECT pp.preferred_gender FROM private_profiles pp WHERE pp.user_id = matching_preferences.user_id),
            'ANY'
        )
        """
    )
    with op.batch_alter_table("matching_preferences", schema=None) as batch_op:
        batch_op.alter_column("preferred_gender", existing_type=sa.String(length=10), nullable=False)
    with op.batch_alter_table("private_profiles", schema=None) as batch_op:
        batch_op.drop_column("preferred_gender")
