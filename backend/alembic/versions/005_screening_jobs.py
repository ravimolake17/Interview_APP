"""Add screening_jobs queue table for async Agent 1 evaluations."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_screening_jobs"
down_revision: Union[str, None] = "004_candidate_file_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "screening_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screening_jobs_status", "screening_jobs", ["status"])
    op.create_index("ix_screening_jobs_created_at", "screening_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_screening_jobs_created_at", table_name="screening_jobs")
    op.drop_index("ix_screening_jobs_status", table_name="screening_jobs")
    op.drop_table("screening_jobs")
