"""Add interview_blueprint table for Agent 3."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_interview_blueprint"
down_revision: Union[str, None] = "009_job_postings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_blueprint",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("blueprint_version", sa.String(length=16), nullable=False),
        sa.Column("candidate_level", sa.String(length=32), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("blueprint_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.candidate_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_blueprint_candidate_id",
        "interview_blueprint",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_blueprint_candidate_id", table_name="interview_blueprint")
    op.drop_table("interview_blueprint")
