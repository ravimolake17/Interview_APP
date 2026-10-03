"""Add interview_question_sets for Agent 4."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_interview_question_sets"
down_revision: Union[str, None] = "013_audit_user_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_question_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("blueprint_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("candidate_level", sa.String(length=32), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("total_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("questions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["blueprint_id"], ["interview_blueprint.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.candidate_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_question_sets_candidate_id",
        "interview_question_sets",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_question_sets_candidate_id", table_name="interview_question_sets")
    op.drop_table("interview_question_sets")
