"""Add SUPERADMIN role, departments catalog, and seed SuperAdmin."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_superadmin_departments"
down_revision: Union[str, None] = "018_hr_recommendation_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_DEPARTMENTS: list[tuple[str, str]] = [
    ("Engineering", "Software, platform, and application development"),
    ("Product", "Product management and strategy"),
    ("Design", "Visual, product, and brand design"),
    ("UX Research", "User research and experience insights"),
    ("AI/ML", "Machine learning, LLMs, and applied AI"),
    ("Data Science", "Modeling, experimentation, and data products"),
    ("Analytics", "Business intelligence and reporting"),
    ("Infrastructure", "Cloud, networking, and platform reliability"),
    ("DevOps", "CI/CD, release engineering, and automation"),
    ("Cloud & Platform", "Cloud architecture and internal developer platforms"),
    ("Cybersecurity", "Security operations, GRC, and application security"),
    ("Quality Assurance", "QA, test automation, and quality engineering"),
    ("IT Support", "End-user computing and internal IT"),
    ("Human Resources", "People operations and employee experience"),
    ("Talent Acquisition", "Recruiting, sourcing, and hiring operations"),
    ("Finance", "Accounting, FP&A, and payroll"),
    ("Legal & Compliance", "Legal, contracts, and regulatory compliance"),
    ("Sales", "Revenue and account management"),
    ("Business Development", "Partnerships and growth"),
    ("Marketing", "Brand, demand generation, and communications"),
    ("Customer Success", "Onboarding, support, and customer outcomes"),
    ("Operations", "Business and process operations"),
    ("Procurement", "Vendor management and purchasing"),
    ("Administration", "Office administration and facilities coordination"),
    ("Research & Development", "Applied research and innovation"),
    ("Content", "Content strategy, technical writing, and documentation"),
    ("Facilities", "Workplace and facilities management"),
]

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

    departments = sa.table(
        "departments",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        departments,
        [
            {
                "name": name,
                "description": description,
                "is_active": True,
                "sort_order": index,
            }
            for index, (name, description) in enumerate(DEFAULT_DEPARTMENTS)
        ],
    )

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
