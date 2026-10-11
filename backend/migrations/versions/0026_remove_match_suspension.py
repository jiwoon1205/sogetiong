"""매칭 정지 기능 없애기 (2026-10-12)

- 남아 있던 숨김 매칭(HIDDEN)을 모두 공개(ACTIVE)하고, 두 사람에게 "새로운 매칭" 알림을 넣는다
  (서로 LIKE해서 생긴 매칭이라 공개한다. 휴대폰 알림은 보내지 않는다 — 사이트에 들어오면 알림·축하 화면으로 본다)
- 모든 사용자의 매칭 정지를 해제한다. users.match_suspended 칸은 남겨 두지만 더는 쓰지 않는다
- 되돌리기(downgrade)는 하지 않는다 (공개한 매칭을 다시 숨길 수 없음)

Revision ID: 0026_remove_match_suspension
Revises: 0025_super_like
Create Date: 2026-10-12
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_remove_match_suspension"
down_revision: Union[str, None] = "0025_super_like"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

matches = sa.table(
    "matches",
    sa.column("id", sa.Uuid()),
    sa.column("user_a_id", sa.Uuid()),
    sa.column("user_b_id", sa.Uuid()),
    sa.column("status", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
notifications = sa.table(
    "notifications",
    sa.column("id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("type", sa.String()),
    sa.column("title", sa.String()),
    sa.column("body", sa.Text()),
    sa.column("related_id", sa.Uuid()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
users = sa.table(
    "users",
    sa.column("match_suspended", sa.Boolean()),
    sa.column("match_suspended_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    hidden = conn.execute(sa.select(matches.c.id, matches.c.user_a_id, matches.c.user_b_id).where(matches.c.status == "HIDDEN")).all()
    rows = []
    for match_id, a, b in hidden:
        for uid in (a, b):
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "user_id": uid,
                    "type": "MATCH_CREATED",
                    "title": "새로운 매칭이 생겼어요",
                    "body": "서로 LIKE를 보내 매칭되었습니다. 대화를 시작해보세요.",
                    "related_id": match_id,
                    "created_at": now,
                }
            )
    if hidden:
        conn.execute(matches.update().where(matches.c.status == "HIDDEN").values(status="ACTIVE", updated_at=now))
    if rows:
        op.bulk_insert(notifications, rows)
    conn.execute(users.update().values(match_suspended=False, match_suspended_at=None))


def downgrade() -> None:
    pass
