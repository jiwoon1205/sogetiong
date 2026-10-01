"""하루 접속 기록 표 (2026-10-01)

- user_daily_visits(user_id, visit_date): 한 사람이 하루(한국 시간)에 한 줄만 쌓인다.
  추천 순서의 "활동 점수"(최근 14일 중 며칠 접속했나)와
  관리자 대시보드의 "활성 사용자"(최근 7일 안에 접속한 사람)에 쓴다.
- 기존 사용자는 마지막 접속 시각(last_active_at)이 있는 날 하루만 채운다.
  (그 전 기록은 남아 있지 않으므로, 다음 접속부터 쌓인다)

Revision ID: 0011_user_daily_visits
Revises: 0010_user_last_active
Create Date: 2026-10-01
"""
from datetime import timedelta, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_user_daily_visits"
down_revision: Union[str, None] = "0010_user_last_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KST = timezone(timedelta(hours=9))


def upgrade() -> None:
    op.create_table(
        "user_daily_visits",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "visit_date"),
    )
    op.create_index("ix_user_daily_visits_visit_date", "user_daily_visits", ["visit_date"])

    # 기존 사용자: 마지막 접속한 날(한국 시간)을 한 줄 넣는다.
    # SQL로 시간대를 바꾸면 DB마다 문법이 달라서, 파이썬에서 계산한다 (사용자 수가 적어 금방 끝난다).
    bind = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Uuid()), sa.column("last_active_at", sa.DateTime(timezone=True)))
    visits = sa.table("user_daily_visits", sa.column("user_id", sa.Uuid()), sa.column("visit_date", sa.Date()))
    rows = bind.execute(sa.select(users.c.id, users.c.last_active_at).where(users.c.last_active_at.isnot(None))).all()
    values = []
    for user_id, last_active in rows:
        if last_active.tzinfo is None:  # SQLite는 시간대 없이 돌려준다 (UTC로 저장됨)
            last_active = last_active.replace(tzinfo=timezone.utc)
        values.append({"user_id": user_id, "visit_date": last_active.astimezone(KST).date()})
    if values:
        op.bulk_insert(visits, values)


def downgrade() -> None:
    op.drop_index("ix_user_daily_visits_visit_date", table_name="user_daily_visits")
    op.drop_table("user_daily_visits")
