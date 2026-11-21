"""게시판 답글 (2026-11-22): board_comments에 parent_id(어느 댓글 밑인지) · reply_to_user_id(누구에게) 추가.

Revision ID: 0046_board_replies
Revises: 0045_sns_platform
Create Date: 2026-11-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_board_replies"
down_revision: Union[str, None] = "0045_sns_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("board_comments") as batch:
        batch.add_column(sa.Column("parent_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("reply_to_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_board_comments_parent", "board_comments", ["parent_id"], ["id"])
        batch.create_foreign_key("fk_board_comments_reply_to_user", "users", ["reply_to_user_id"], ["id"])
        batch.create_index("ix_board_comments_parent_id", ["parent_id"])


def downgrade() -> None:
    with op.batch_alter_table("board_comments") as batch:
        batch.drop_index("ix_board_comments_parent_id")
        batch.drop_constraint("fk_board_comments_reply_to_user", type_="foreignkey")
        batch.drop_constraint("fk_board_comments_parent", type_="foreignkey")
        batch.drop_column("reply_to_user_id")
        batch.drop_column("parent_id")
