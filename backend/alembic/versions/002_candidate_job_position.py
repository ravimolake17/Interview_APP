"""Add job_position column to candidate table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_candidate_job_position"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate", sa.Column("job_position", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate", "job_position")
