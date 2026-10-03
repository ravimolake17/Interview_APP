"""Add NEEDS_REVIEW status and HR review fields on candidate."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_candidate_hr_review"
down_revision: Union[str, None] = "002_candidate_job_position"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE candidate_status ADD VALUE IF NOT EXISTS 'NEEDS_REVIEW'")
    op.add_column("candidate", sa.Column("jd_text", sa.Text(), nullable=True))
    op.add_column(
        "candidate",
        sa.Column("evaluation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate", "evaluation_snapshot")
    op.drop_column("candidate", "jd_text")
