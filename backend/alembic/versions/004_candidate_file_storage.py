"""Add stored resume and JD file metadata to candidate."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_candidate_file_storage"
down_revision: Union[str, None] = "003_candidate_hr_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate", sa.Column("resume_original_filename", sa.String(length=255), nullable=True))
    op.add_column("candidate", sa.Column("resume_file_url", sa.String(length=512), nullable=True))
    op.add_column("candidate", sa.Column("jd_original_filename", sa.String(length=255), nullable=True))
    op.add_column("candidate", sa.Column("jd_file_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate", "jd_file_url")
    op.drop_column("candidate", "jd_original_filename")
    op.drop_column("candidate", "resume_file_url")
    op.drop_column("candidate", "resume_original_filename")
