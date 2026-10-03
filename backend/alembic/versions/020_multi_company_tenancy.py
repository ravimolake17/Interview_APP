"""Multi-company tenancy: companies table, company_id FKs, RR Parkon backfill, RR Kabel seed."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020_multi_company_tenancy"
down_revision: Union[str, None] = "019_superadmin_departments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = (
    "departments",
    "job_postings",
    "candidate",
    "interview",
    "available_slots",
    "interview_blueprint",
    "interview_evaluations",
    "interview_question_sets",
    "hr_recommendation_reports",
)

OPTIONAL_TENANT_TABLES = (
    "users",
    "audit_logs",
    "screening_jobs",
)

CHILD_BACKFILL = (
    ("interview", "candidate_id", "candidate", "candidate_id"),
    ("interview_blueprint", "candidate_id", "candidate", "candidate_id"),
    ("interview_evaluations", "candidate_id", "candidate", "candidate_id"),
    ("interview_question_sets", "candidate_id", "candidate", "candidate_id"),
    ("hr_recommendation_reports", "candidate_id", "candidate", "candidate_id"),
)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("logo", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
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
        sa.UniqueConstraint("code", name="uq_companies_code"),
    )
    op.create_index("ix_companies_status", "companies", ["status"], unique=False)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO companies (name, code, status)
            VALUES
                ('RR Parkon', 'RRPARKON', 'active'),
                ('RR Kabel', 'RRKABEL', 'active')
            """
        )
    )
    parkon_id = bind.execute(
        sa.text("SELECT id FROM companies WHERE code = 'RRPARKON'")
    ).scalar_one()
    kabel_id = bind.execute(
        sa.text("SELECT id FROM companies WHERE code = 'RRKABEL'")
    ).scalar_one()

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'COMPANY_ADMIN'")

    for table in TENANT_TABLES + OPTIONAL_TENANT_TABLES:
        op.add_column(table, sa.Column("company_id", sa.Integer(), nullable=True))

    bind.execute(
        sa.text("UPDATE users SET company_id = :cid WHERE role <> 'SUPERADMIN'"),
        {"cid": parkon_id},
    )
    bind.execute(sa.text("UPDATE users SET role = 'COMPANY_ADMIN' WHERE role = 'ADMIN'"))

    for table in (
        "departments",
        "job_postings",
        "candidate",
        "available_slots",
        "screening_jobs",
        "audit_logs",
    ):
        bind.execute(
            sa.text(f"UPDATE {table} SET company_id = :cid WHERE company_id IS NULL"),
            {"cid": parkon_id},
        )

    for child, child_key, parent, parent_key in CHILD_BACKFILL:
        bind.execute(
            sa.text(
                f"""
                UPDATE {child} AS c
                SET company_id = p.company_id
                FROM {parent} AS p
                WHERE c.{child_key} = p.{parent_key}
                  AND c.company_id IS NULL
                """
            )
        )
        bind.execute(
            sa.text(f"UPDATE {child} SET company_id = :cid WHERE company_id IS NULL"),
            {"cid": parkon_id},
        )

    for table in TENANT_TABLES:
        op.alter_column(table, "company_id", existing_type=sa.Integer(), nullable=False)

    for table in TENANT_TABLES + OPTIONAL_TENANT_TABLES:
        op.create_foreign_key(
            f"fk_{table}_company_id",
            table,
            "companies",
            ["company_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_company_id", table, ["company_id"], unique=False)

    op.create_index("ix_candidate_company_status", "candidate", ["company_id", "status"], unique=False)
    op.create_index(
        "ix_candidate_company_created_at",
        "candidate",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_company_created_at",
        "audit_logs",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_job_postings_company_status",
        "job_postings",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index("ix_users_company_id_role", "users", ["company_id", "role"], unique=False)

    op.drop_index("ix_departments_name", table_name="departments")
    op.create_index("ix_departments_name", "departments", ["name"], unique=False)
    op.create_unique_constraint("uq_departments_company_name", "departments", ["company_id", "name"])

    op.drop_constraint("uq_slot_date_start", "available_slots", type_="unique")
    op.create_unique_constraint(
        "uq_slot_company_date_start",
        "available_slots",
        ["company_id", "date", "start_time"],
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO departments (company_id, name, description, is_active, sort_order)
            SELECT :kabel_id, name, description, is_active, sort_order
            FROM departments
            WHERE company_id = :parkon_id
            """
        ),
        {"kabel_id": kabel_id, "parkon_id": parkon_id},
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO application_settings (scope_key, namespace, data, updated_by_user_id)
            SELECT :parkon_scope, namespace, data, updated_by_user_id
            FROM application_settings
            WHERE scope_key = 'global'
              AND namespace IN ('company', 'interview_availability', 'screening_policy', 'notifications')
              AND NOT EXISTS (
                  SELECT 1 FROM application_settings s
                  WHERE s.scope_key = :parkon_scope AND s.namespace = application_settings.namespace
              )
            """
        ),
        {"parkon_scope": f"company:{parkon_id}"},
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO application_settings (scope_key, namespace, data, updated_by_user_id)
            SELECT :kabel_scope, namespace, data, updated_by_user_id
            FROM application_settings
            WHERE scope_key = :parkon_scope
              AND namespace IN ('interview_availability', 'screening_policy', 'notifications')
              AND NOT EXISTS (
                  SELECT 1 FROM application_settings s
                  WHERE s.scope_key = :kabel_scope AND s.namespace = application_settings.namespace
              )
            """
        ),
        {
            "kabel_scope": f"company:{kabel_id}",
            "parkon_scope": f"company:{parkon_id}",
        },
    )


def downgrade() -> None:
    op.drop_constraint("uq_slot_company_date_start", "available_slots", type_="unique")
    op.create_unique_constraint("uq_slot_date_start", "available_slots", ["date", "start_time"])
    op.drop_constraint("uq_departments_company_name", "departments", type_="unique")
    op.drop_index("ix_departments_name", table_name="departments")
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)

    op.drop_index("ix_users_company_id_role", table_name="users")
    op.drop_index("ix_job_postings_company_status", table_name="job_postings")
    op.drop_index("ix_audit_logs_company_created_at", table_name="audit_logs")
    op.drop_index("ix_candidate_company_created_at", table_name="candidate")
    op.drop_index("ix_candidate_company_status", table_name="candidate")

    for table in TENANT_TABLES + OPTIONAL_TENANT_TABLES:
        op.drop_index(f"ix_{table}_company_id", table_name=table)
        op.drop_constraint(f"fk_{table}_company_id", table, type_="foreignkey")
        op.drop_column(table, "company_id")

    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_table("companies")
