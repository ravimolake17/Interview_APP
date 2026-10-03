"""Add user_name to audit_logs and backfill from users."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_audit_user_name"
down_revision: Union[str, None] = "012_audit_log_enrichment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("user_name", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE audit_logs AS a
        SET user_name = u.full_name
        FROM users AS u
        WHERE a.user_id = u.id
          AND a.user_name IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "user_name")
