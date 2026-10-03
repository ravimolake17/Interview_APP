"""Add enriched audit-log columns (role, UA, session, request, status, values, location)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_audit_log_enrichment"
down_revision: Union[str, None] = "011_application_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("user_role", sa.String(length=32), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.add_column("audit_logs", sa.Column("session_id", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="SUCCESS"),
    )
    op.add_column("audit_logs", sa.Column("location", sa.String(length=255), nullable=True))

    op.create_index("ix_audit_logs_session_id", "audit_logs", ["session_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_status", "audit_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_status", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_session_id", table_name="audit_logs")
    op.drop_column("audit_logs", "location")
    op.drop_column("audit_logs", "status")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "session_id")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "new_value")
    op.drop_column("audit_logs", "old_value")
    op.drop_column("audit_logs", "user_role")
