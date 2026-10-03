"""Add profile fields and persistent application settings."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_application_settings"
down_revision: Union[str, None] = "010_interview_blueprint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("job_title", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))

    op.create_table(
        "application_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope_key", sa.String(length=64), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_key",
            "namespace",
            name="uq_application_setting_scope_namespace",
        ),
    )
    op.create_index(
        "ix_application_settings_scope_key",
        "application_settings",
        ["scope_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_settings_scope_key", table_name="application_settings")
    op.drop_table("application_settings")
    op.drop_column("users", "phone")
    op.drop_column("users", "job_title")
