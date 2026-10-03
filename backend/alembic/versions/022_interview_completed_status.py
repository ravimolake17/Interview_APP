"""Add INTERVIEW_COMPLETED to candidate_status."""

from typing import Sequence, Union

from alembic import op

revision: str = "022_interview_completed_status"
down_revision: Union[str, None] = "021_kabel_own_departments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE candidate_status ADD VALUE IF NOT EXISTS 'INTERVIEW_COMPLETED'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value safely while rows may still use it.
    pass
