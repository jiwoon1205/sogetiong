"""여성 회원 무료 · 성별 고정 · 항상 이성 추천 (2026-11-07)

1) '원하는 성별'을 없앴다 → 모든 사람의 private_profiles.preferred_gender를 자기 성별의 반대로 맞춘다.
   예전에 '상관없음'이나 같은 성별을 골랐던 사람에게는 사이트 안 알림으로 알려 준다.
2) 여성 회원은 이제 기본 이용권이 무료다 (상시). 남아 있던 기본 이용권 기간은 VIP로 바꿔 준다
   → vip_until = max(vip_until, member_until). (VIP에는 기본이 포함돼서 member_until은 그대로 둬도 된다)
   바꿔 준 사람에게 알림. 쌓아 둔 일수(member_days_banked)는 추천이 열릴 때 VIP로 시작한다 (membership_service.start_banked).
3) 탈퇴하지 않은 여성 회원 모두에게 "기본 이용권 무료" 알림.

되돌리기(downgrade)는 하지 않는다 (예전 '원하는 성별' 값을 따로 남기지 않음 — 바꾼 사람 목록은 알림에 남는다).

Revision ID: 0030_female_free_gender_lock
Revises: 0029_relationship_goal
Create Date: 2026-11-07
"""
import math
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_female_free_gender_lock"
down_revision: Union[str, None] = "0029_relationship_goal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

users = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("status", sa.String()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("member_until", sa.DateTime(timezone=True)),
    sa.column("vip_until", sa.DateTime(timezone=True)),
)
public_profiles = sa.table(
    "public_profiles",
    sa.column("user_id", sa.Uuid()),
    sa.column("gender", sa.String()),
)
private_profiles = sa.table(
    "private_profiles",
    sa.column("user_id", sa.Uuid()),
    sa.column("preferred_gender", sa.String()),
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


def _utc(t: datetime | None) -> datetime | None:
    if t is None:
        return None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    alerts = []

    def alert(uid, title: str, body: str) -> None:
        alerts.append(
            {
                "id": uuid.uuid4(),
                "user_id": uid,
                "type": "ACCOUNT_STATUS",
                "title": title,
                "body": body,
                "related_id": None,
                "created_at": now,
            }
        )

    rows = conn.execute(
        sa.select(
            users.c.id,
            users.c.status,
            users.c.deleted_at,
            users.c.member_until,
            users.c.vip_until,
            public_profiles.c.gender,
            private_profiles.c.preferred_gender,
        )
        .select_from(users)
        .join(public_profiles, public_profiles.c.user_id == users.c.id)
        .outerjoin(private_profiles, private_profiles.c.user_id == users.c.id)
    ).all()

    for uid, status, deleted_at, member_until, vip_until, gender, preferred in rows:
        if gender not in ("MALE", "FEMALE"):
            continue
        alive = status != "DELETED" and deleted_at is None
        # 1) 항상 이성
        target = "MALE" if gender == "FEMALE" else "FEMALE"
        if preferred is not None and preferred != target:
            conn.execute(
                private_profiles.update().where(private_profiles.c.user_id == uid).values(preferred_gender=target)
            )
            if alive:
                alert(
                    uid,
                    "추천 상대 기준이 바뀌었어요",
                    "이제 훕팅은 이성만 추천해요. '원하는 성별' 선택이 없어져서, 이미 생긴 매칭·대화는 그대로 두고 "
                    "앞으로의 추천부터 이성만 보여드려요.",
                )
        if gender != "FEMALE" or not alive:
            continue
        # 2) 여성: 남은 기본 이용권 기간 → VIP
        member_until, vip_until = _utc(member_until), _utc(vip_until)
        vip_end = vip_until if vip_until is not None and vip_until > now else now
        if member_until is not None and member_until > vip_end:
            days = math.ceil((member_until - vip_end).total_seconds() / 86400)
            conn.execute(users.update().where(users.c.id == uid).values(vip_until=member_until))
            alert(
                uid,
                "남은 이용권 기간을 VIP로 바꿔드렸어요",
                f"여성 회원은 이제 기본 이용권이 무료예요. 남아 있던 기본 이용권 {days}일을 VIP로 바꿔드렸어요.",
            )
        # 3) 여성 회원 무료 안내
        alert(
            uid,
            "여성 회원은 기본 이용권이 무료예요",
            "이제 여성 회원은 이용권을 사지 않아도 하루 좋아요 3개를 무료로 계속 쓸 수 있어요. "
            "VIP도 4,000원으로 살 수 있어요.",
        )

    if alerts:
        op.bulk_insert(notifications, alerts)


def downgrade() -> None:
    pass
