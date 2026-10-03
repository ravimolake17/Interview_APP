"""Remove Parkon starter departments cloned onto RR Kabel."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021_kabel_own_departments"
down_revision: Union[str, None] = "020_multi_company_tenancy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    kabel_id = bind.execute(sa.text("SELECT id FROM companies WHERE code = 'RRKABEL'")).scalar()
    parkon_id = bind.execute(sa.text("SELECT id FROM companies WHERE code = 'RRPARKON'")).scalar()
    if not kabel_id or not parkon_id:
        return
    bind.execute(
        sa.text(
            """
            DELETE FROM departments
            WHERE company_id = :kabel_id
              AND LOWER(name) IN (
                  SELECT LOWER(name) FROM departments WHERE company_id = :parkon_id
              )
            """
        ),
        {"kabel_id": kabel_id, "parkon_id": parkon_id},
    )


def downgrade() -> None:
    bind = op.get_bind()
    kabel_id = bind.execute(sa.text("SELECT id FROM companies WHERE code = 'RRKABEL'")).scalar()
    parkon_id = bind.execute(sa.text("SELECT id FROM companies WHERE code = 'RRPARKON'")).scalar()
    if not kabel_id or not parkon_id:
        return
    bind.execute(
        sa.text(
            """
            INSERT INTO departments (company_id, name, description, is_active, sort_order)
            SELECT :kabel_id, name, description, is_active, sort_order
            FROM departments
            WHERE company_id = :parkon_id
              AND LOWER(name) NOT IN (
                  SELECT LOWER(name) FROM departments WHERE company_id = :kabel_id
              )
            """
        ),
        {"kabel_id": kabel_id, "parkon_id": parkon_id},
    )
