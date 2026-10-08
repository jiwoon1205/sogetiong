"""대화방 읽음 기록 (2026-10-08): 대화 목록에 안 읽은 메시지 수 표시

- match_reads(match_id, user_id, last_read_at): 내가 어디까지 읽었나
- 기존 대화는 모두 "읽음"으로 시작한다 (배포하자마자 옛 메시지가 전부 안 읽음으로 뜨지 않게):
  매칭마다 두 사람 모두 last_read_at = 그 대화의 마지막 메시지 시각 (메시지가 없으면 행을 만들지 않는다)

Revision ID: 0022_match_reads
Revises: 0021_free_trial
Create Date: 2026-10-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_match_reads"
down_revision: Union[str, None] = "0021_free_trial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_reads",
        sa.Column("match_id", sa.Uuid(), sa.ForeignKey("matches.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
    )
    for col in ("user_a_id", "user_b_id"):
        op.execute(
            f"""
            INSERT INTO match_reads (match_id, user_id, last_read_at)
            SELECT m.id, m.{col}, MAX(msg.created_at)
            FROM matches m JOIN messages msg ON msg.match_id = m.id
            GROUP BY m.id, m.{col}
            """
        )


def downgrade() -> None:
    op.drop_table("match_reads")
