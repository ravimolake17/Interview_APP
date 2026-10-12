"""Add SUPERADMIN role, departments catalog, and seed SuperAdmin."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_superadmin_departments"
down_revision: Union[str, None] = "018_hr_recommendation_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SuperAdmin@1234
SUPERADMIN_HASH = "$2b$12$J7zUmUun85aTiNNDfRigwuhe6TOUk7bIPqzKH476uGEzW0LfingJ2"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'SUPERADMIN'")

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)
    # Departments are managed only via SuperAdmin UI — no starter catalog seed.

    users = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": "superadmin@rrglobal.com"},
    ).first()
    if existing is None:
        bind.execute(
            users.insert().values(
                email="superadmin@rrglobal.com",
                full_name="Super Admin",
                password_hash=SUPERADMIN_HASH,
                role="SUPERADMIN",
                is_active=True,
            )
        )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'superadmin@rrglobal.com'")
    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_table("departments")
