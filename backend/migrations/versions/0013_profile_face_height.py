"""프로필에 얼굴상·키 추가 (2026-10-02)

둘 다 선택사항이라 비어 있어도 된다 (기존 사용자는 모두 비어 있는 상태로 시작).
- face_type: 강아지상·고양이상 등 10개 중 하나 (목록은 app/schemas/profile.py의 FACE_TYPES)
- height_cm: 키 (cm, 140~210)
걸러보기·추천 순서에는 쓰지 않는다.

Revision ID: 0013_profile_face_height
Revises: 0012_user_deleted_snapshot
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_profile_face_height"
down_revision: Union[str, None] = "0012_user_deleted_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("face_type", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("height_cm", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("public_profiles", schema=None) as batch_op:
        batch_op.drop_column("height_cm")
        batch_op.drop_column("face_type")
