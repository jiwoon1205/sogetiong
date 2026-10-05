"""사용자 설문 (2026-10-05)

- app_settings: 관리자 화면에서 켜고 끄는 설정 (지금은 survey_open 하나)
- survey_responses: 설문 응답. 계정 하나당 설문 하나에 한 번만

Revision ID: 0018_survey
Revises: 0017_match_suspension
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_survey"
down_revision: Union[str, None] = "0017_match_suspension"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=60), primary_key=True),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("survey_key", sa.String(length=60), nullable=False),
        sa.Column("appearance_choice", sa.String(length=30), nullable=False),
        sa.Column("appearance_comment", sa.Text(), nullable=True),
        sa.Column("payment_rating", sa.Integer(), nullable=False),
        sa.Column("payment_comment", sa.Text(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "survey_key", name="uq_survey_responses_user_survey"),
    )
    op.create_index("ix_survey_responses_user_id", "survey_responses", ["user_id"])
    op.create_index("ix_survey_responses_survey_key", "survey_responses", ["survey_key"])


def downgrade() -> None:
    op.drop_index("ix_survey_responses_survey_key", table_name="survey_responses")
    op.drop_index("ix_survey_responses_user_id", table_name="survey_responses")
    op.drop_table("survey_responses")
    op.drop_table("app_settings")
