"""Seed default HR and admin users in the database."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_seed_users"
down_revision: Union[str, None] = "006_auth_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# bcrypt hash for initial password "changeme" — change after first login
DEFAULT_PASSWORD_HASH = "$2b$12$xN0bfIulmMXsNdgYEzAtrOzPM/QRMs65RxZW1FBk9IZgPQTyovY1i"

user_role = postgresql.ENUM("HR", "ADMIN", name="user_role", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar()
    if count and count > 0:
        return

    users = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role", user_role),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        users,
        [
            {
                "email": "hr@company.com",
                "full_name": "HR User",
                "password_hash": DEFAULT_PASSWORD_HASH,
                "role": "HR",
                "is_active": True,
            },
            {
                "email": "admin@company.com",
                "full_name": "System Admin",
                "password_hash": DEFAULT_PASSWORD_HASH,
                "role": "ADMIN",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM users WHERE email IN ('hr@company.com', 'admin@company.com')"
        )
    )
