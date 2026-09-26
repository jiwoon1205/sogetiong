"""관리자 권한에 chats:read(대화 열람) 추가 — SUPER_ADMIN, MODERATOR

역할별 권한은 DB(admin_roles)에 저장되어 있으므로, 코드의 권한표만 바꿔서는
이미 만들어진 DB에 반영되지 않는다. 그래서 여기서 직접 추가한다.

Revision ID: 0004_chats_read_permission
Revises: 0003_user_email_hash
Create Date: 2026-09-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_chats_read_permission"
down_revision: Union[str, None] = "0003_user_email_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION = "chats:read"
ROLES = ("SUPER_ADMIN", "MODERATOR")

roles = sa.table("admin_roles", sa.column("id", sa.Uuid()), sa.column("name", sa.String()), sa.column("permissions_json", sa.JSON()))


def _change(add: bool) -> None:
    conn = op.get_bind()
    for row in conn.execute(sa.select(roles.c.id, roles.c.permissions_json).where(roles.c.name.in_(ROLES))).fetchall():
        perms = [p for p in (row.permissions_json or []) if p != PERMISSION]
        if add:
            perms.append(PERMISSION)
        conn.execute(roles.update().where(roles.c.id == row.id).values(permissions_json=perms))


def upgrade() -> None:
    _change(add=True)


def downgrade() -> None:
    _change(add=False)
