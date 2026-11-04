"""Add explicit activity category to the governed factor registry."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0006"
down_revision = "20261104_0005"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("emission_factors")
    }
    if "activity_category" not in columns:
        op.add_column(
            "emission_factors",
            sa.Column("activity_category", sa.String(64), nullable=True),
        )
    op.execute("""
        UPDATE emission_factors
        SET activity_category = CASE
          WHEN position(':' in name) > 0 THEN trim(split_part(name, ':', 1))
          ELSE 'unclassified'
        END
        WHERE activity_category IS NULL
    """)
    op.alter_column("emission_factors", "activity_category", nullable=False)


def downgrade():
    op.drop_column("emission_factors", "activity_category")
