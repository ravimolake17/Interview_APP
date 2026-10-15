"""Company interview intro + department interview brief for Agent 4 Q&A."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024_company_dept_interview_briefs"
down_revision: Union[str, None] = "023_no_default_department_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("interview_intro", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("interview_intro_spoken", sa.Text(), nullable=True))
    op.add_column("departments", sa.Column("interview_brief", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("departments", "interview_brief")
    op.drop_column("companies", "interview_intro_spoken")
    op.drop_column("companies", "interview_intro")
