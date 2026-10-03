"""Add interview_question_audio for pre-generated Kokoro TTS cache."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_interview_question_audio"
down_revision: Union[str, None] = "015_interview_evaluations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_question_audio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("question_set_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("voice", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidate.candidate_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_set_id"], ["interview_question_sets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_set_id",
            "question_id",
            name="uq_question_audio_set_question",
        ),
    )
    op.create_index(
        "ix_interview_question_audio_candidate_id",
        "interview_question_audio",
        ["candidate_id"],
    )
    op.create_index(
        "ix_interview_question_audio_question_set_id",
        "interview_question_audio",
        ["question_set_id"],
    )
    op.create_index(
        "ix_interview_question_audio_question_id",
        "interview_question_audio",
        ["question_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_question_audio_question_id", table_name="interview_question_audio")
    op.drop_index(
        "ix_interview_question_audio_question_set_id", table_name="interview_question_audio"
    )
    op.drop_index(
        "ix_interview_question_audio_candidate_id", table_name="interview_question_audio"
    )
    op.drop_table("interview_question_audio")
