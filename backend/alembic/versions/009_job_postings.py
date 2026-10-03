"""Add job_postings table for HR job listings."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_job_postings"
down_revision: Union[str, None] = "008_rrglobal_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

job_posting_status = postgresql.ENUM(
    "Active",
    "Draft",
    "Closed",
    name="job_posting_status",
    create_type=False,
)


def upgrade() -> None:
    job_posting_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("experience", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", job_posting_status, nullable=False, server_default="Active"),
        sa.Column("jd_original_filename", sa.String(length=255), nullable=True),
        sa.Column("jd_file_url", sa.String(length=512), nullable=True),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("parsed_jd", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_postings_title", "job_postings", ["title"])


def downgrade() -> None:
    op.drop_index("ix_job_postings_title", table_name="job_postings")
    op.drop_table("job_postings")
    job_posting_status.drop(op.get_bind(), checkfirst=True)
