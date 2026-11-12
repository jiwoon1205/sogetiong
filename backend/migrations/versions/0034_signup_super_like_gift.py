"""가입 선물 슈퍼 라이크 (2026-11-12)

- 앞으로 처음 가입하는 사람은 가입할 때 슈퍼 라이크 1개를 받는다 (설정 SIGNUP_SUPER_LIKES, api/v1/auth.signup).
- 이 마이그레이션: 2026-11-05 17:49(한국 시간, 요청한 시각에서 7일 전) 이후에 가입한 사람에게도 1개를 넣어 준다.
  탈퇴하지 않은 계정만, 같은 메일로 예전에 가입한 적이 없는 사람만 (탈퇴 후 재가입은 제외). 알림도 남긴다.
  칸을 바꾸지 않으므로 되돌리기(downgrade)는 아무것도 하지 않는다.

Revision ID: 0034_signup_super_like_gift
Revises: 0033_vip_renewal_discount
Create Date: 2026-11-12
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_signup_super_like_gift"
down_revision: Union[str, None] = "0033_vip_renewal_discount"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CUTOFF = datetime(2026, 11, 5, 8, 49, tzinfo=timezone.utc)  # = 2026-11-05 17:49 한국 시간
GIFT = 1

users = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("email_hash", sa.String()),
    sa.column("status", sa.String()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("super_likes", sa.Integer()),
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


def _utc(t):
    if t is None:
        return None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    rows = conn.execute(sa.select(users.c.id, users.c.email_hash, users.c.status, users.c.deleted_at, users.c.created_at, users.c.super_likes)).all()
    # 같은 메일 지문으로 만든 계정이 2개 이상이면 = 탈퇴 후 다시 가입한 사람 → 선물 없음
    per_hash = {}
    for r in rows:
        if r.email_hash:
            per_hash[r.email_hash] = per_hash.get(r.email_hash, 0) + 1
    alerts = []
    for r in rows:
        created = _utc(r.created_at)
        if created is None or created < CUTOFF or r.status != "ACTIVE" or r.deleted_at is not None:
            continue
        if r.email_hash and per_hash.get(r.email_hash, 0) > 1:
            continue
        conn.execute(sa.update(users).where(users.c.id == r.id).values(super_likes=(r.super_likes or 0) + GIFT))
        alerts.append(
            {
                "id": uuid.uuid4(),
                "user_id": r.id,
                "type": "SUPER_LIKE_GIFT",
                "title": "가입 선물로 슈퍼 라이크를 드렸어요",
                "body": "슈퍼 라이크 1개가 들어왔어요. 추천에서 마음에 드는 사람에게 보내면 상대가 좋아요하지 않아도 바로 대화가 열려요.",
                "related_id": None,
                "created_at": now,
            }
        )
    if alerts:
        op.bulk_insert(notifications, alerts)


def downgrade() -> None:
    pass
