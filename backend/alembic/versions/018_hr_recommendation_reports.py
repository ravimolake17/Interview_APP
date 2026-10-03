"""Add hr_recommendation_reports for Agent 7."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018_hr_recommendation_reports"
down_revision: Union[str, None] = "017_interview_join_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_recommendation_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("screening_score", sa.Float(), nullable=False),
        sa.Column("interview_score", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.candidate_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_recommendation_reports_candidate_id",
        "hr_recommendation_reports",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hr_recommendation_reports_candidate_id",
        table_name="hr_recommendation_reports",
    )
    op.drop_table("hr_recommendation_reports")
