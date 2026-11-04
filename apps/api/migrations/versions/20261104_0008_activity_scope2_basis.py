"""Persist Scope 2 accounting basis on activity records."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0008"
down_revision = "20261104_0007"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("activity_records")
    }
    if "scope_2_basis" not in columns:
        op.add_column(
            "activity_records",
            sa.Column("scope_2_basis", sa.String(24), nullable=True),
        )
    op.create_check_constraint(
        "ck_activity_scope2_basis",
        "activity_records",
        "scope_2_basis IS NULL OR (scope = 'scope_2' AND scope_2_basis IN ('location_based', 'market_based'))",
    )


def downgrade():
    op.drop_constraint("ck_activity_scope2_basis", "activity_records", type_="check")
    op.drop_column("activity_records", "scope_2_basis")
