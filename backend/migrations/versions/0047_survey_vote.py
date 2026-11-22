"""찬반 투표 설문 (2026-11-22): survey_responses에 vote 칸 추가 ("대학교 친구" 없애기 찬성/반대).

Revision ID: 0047_survey_vote
Revises: 0046_board_replies
Create Date: 2026-11-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_survey_vote"
down_revision: Union[str, None] = "0046_board_replies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("survey_responses") as batch:
        batch.add_column(sa.Column("vote", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("survey_responses") as batch:
        batch.drop_column("vote")
