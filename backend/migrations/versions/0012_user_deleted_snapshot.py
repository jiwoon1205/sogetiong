"""탈퇴한 사람의 닉네임·성별을 관리자용으로 남기기 (2026-10-01)

탈퇴하면 공개 프로필(닉네임·성별)이 지워져서, 관리자 화면에서
닉네임 검색·성별 필터를 쓰면 탈퇴한 사람이 아예 안 보였다.
탈퇴할 때 이 두 값만 users에 따로 적어 둔다 (관리자만 본다).

- 이미 탈퇴한 사람은 프로필이 지워진 뒤라 채울 수 없다 (닉네임·성별이 "—"로 보인다).

Revision ID: 0012_user_deleted_snapshot
Revises: 0011_user_daily_visits
Create Date: 2026-10-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_user_deleted_snapshot"
down_revision: Union[str, None] = "0011_user_daily_visits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_nickname", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("deleted_gender", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("deleted_gender")
        batch_op.drop_column("deleted_nickname")
