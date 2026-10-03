"""Replace demo users with RR Global HR and admin accounts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_rrglobal_users"
down_revision: Union[str, None] = "007_seed_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_HASH = "$2b$12$s2xWw6r7861r7XEKhrcSD.CmGSAxPRdzyrsSAPSswY4rr442c5pdu"  # rradmin@1234
HR_HASH = "$2b$12$E2CCqooUQxHI2CGIQN6TAue7ptNHD.Ja1VTLSYKfGaxZEsC/Wh7BO"  # rrhr@12345

user_role = postgresql.ENUM("HR", "ADMIN", name="user_role", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM users WHERE email IN "
            "('hr@company.com', 'admin@company.com')"
        )
    )

    users = sa.table(
        "users",
        sa.column("email", sa.String),
        sa.column("full_name", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role", user_role),
        sa.column("is_active", sa.Boolean),
    )

    for row in (
        {
            "email": "admin@rrglobal.com",
            "full_name": "RR Global Admin",
            "password_hash": ADMIN_HASH,
            "role": "ADMIN",
            "is_active": True,
        },
        {
            "email": "rrhr@rrglobal.com",
            "full_name": "RR Global HR",
            "password_hash": HR_HASH,
            "role": "HR",
            "is_active": True,
        },
    ):
        existing = bind.execute(
            sa.text("SELECT id FROM users WHERE email = :email"),
            {"email": row["email"]},
        ).scalar()
        if existing:
            bind.execute(
                sa.text(
                    """
                    UPDATE users
                    SET full_name = :full_name,
                        password_hash = :password_hash,
                        role = :role,
                        is_active = :is_active
                    WHERE email = :email
                    """
                ),
                row,
            )
        else:
            op.bulk_insert(users, [row])


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM users WHERE email IN "
            "('admin@rrglobal.com', 'rrhr@rrglobal.com')"
        )
    )
