"""users.email_hash 추가 + 탈퇴 계정 이메일 익명화

- 모든 계정에 이메일 지문(email_hash)을 채운다.
- 이미 탈퇴한 계정은 이메일을 가짜 주소로 바꿔서, 같은 학교 메일로 다시 가입할 수 있게 한다.

Revision ID: 0003_user_email_hash
Revises: 0002_verification_purpose
Create Date: 2026-09-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_email_hash"
down_revision: Union[str, None] = "0002_verification_purpose"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.services.auth_service import anonymized_email, email_fingerprint

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email_hash", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_email_hash"), ["email_hash"], unique=False)

    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("email_hash", sa.String()),
        sa.column("status", sa.String()),
    )
    conn = op.get_bind()
    for row in conn.execute(sa.select(users.c.id, users.c.email, users.c.status)).fetchall():
        values = {"email_hash": email_fingerprint(row.email)}
        if row.status == "DELETED":
            values["email"] = anonymized_email(row.id)
        conn.execute(users.update().where(users.c.id == row.id).values(**values))


def downgrade() -> None:
    # 익명화한 이메일은 되돌릴 수 없다 (원래 주소를 보관하지 않으므로)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_email_hash"))
        batch_op.drop_column("email_hash")
