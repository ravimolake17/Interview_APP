"""Document that departments are UI-managed only (no starter seed).

Revision 019 previously bulk-inserted a hardcoded catalog. That insert was
removed from 019 for fresh installs. This revision does not insert or delete
rows — existing environments keep whatever SuperAdmin already configured.
"""

from typing import Sequence, Union

revision: str = "023_no_default_department_seed"
down_revision: Union[str, None] = "022_interview_completed_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty: do not re-seed departments on migrate.
    pass


def downgrade() -> None:
    pass
