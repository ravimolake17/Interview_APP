"""Add hashed interview join token columns."""

from alembic import op
import sqlalchemy as sa

revision = "017_interview_join_token"
down_revision = "016_interview_question_audio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview", sa.Column("join_token_hash", sa.String(length=128), nullable=True))
    op.add_column("interview", sa.Column("join_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_interview_join_token_hash", "interview", ["join_token_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_join_token_hash", table_name="interview")
    op.drop_column("interview", "join_token_expires_at")
    op.drop_column("interview", "join_token_hash")
