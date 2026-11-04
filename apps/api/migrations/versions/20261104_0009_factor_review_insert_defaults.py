"""Add NULL server defaults to reviewer-only factor columns."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0009"
down_revision = "20261104_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("emission_factors", "approved_by", server_default=sa.text("NULL"))
    op.alter_column("emission_factors", "approved_at", server_default=sa.text("NULL"))
    op.alter_column("emission_factors", "approval_note", server_default=sa.text("NULL"))


def downgrade():
    op.alter_column("emission_factors", "approval_note", server_default=None)
    op.alter_column("emission_factors", "approved_at", server_default=None)
    op.alter_column("emission_factors", "approved_by", server_default=None)
