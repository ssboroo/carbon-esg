"""Add separate location-based and market-based Scope 2 accounting outputs."""

from alembic import op
import sqlalchemy as sa

revision = "0005_scope2_dual_method_reporting"
down_revision = "0004_evidence_vault"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("emission_factors", sa.Column("scope_2_method", sa.String(24), nullable=True))
    op.add_column("activity_records", sa.Column("scope_2_method", sa.String(24), nullable=True))
    op.add_column(
        "inventories",
        sa.Column(
            "scope_2_primary_method",
            sa.String(24),
            nullable=False,
            server_default="location_based",
        ),
    )
    op.add_column("calculation_runs", sa.Column("scope_2_location_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("scope_2_market_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("total_location_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("total_market_based_kgco2e", sa.Numeric(24, 8), nullable=True))

    op.create_check_constraint(
        "ck_factor_scope_2_method",
        "emission_factors",
        "((scope = 'scope_1' AND scope_2_method IS NULL) OR "
        "(scope = 'scope_2' AND (scope_2_method IS NULL OR scope_2_method IN ('location_based', 'market_based'))))",
    )
    op.create_check_constraint(
        "ck_activity_scope_2_method",
        "activity_records",
        "((scope = 'scope_1' AND scope_2_method IS NULL) OR "
        "(scope = 'scope_2' AND (scope_2_method IS NULL OR scope_2_method IN ('location_based', 'market_based'))))",
    )
    op.create_check_constraint(
        "ck_inventory_scope_2_primary_method",
        "inventories",
        "scope_2_primary_method IN ('location_based', 'market_based')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_inventory_scope_2_primary_method", "inventories", type_="check")
    op.drop_constraint("ck_activity_scope_2_method", "activity_records", type_="check")
    op.drop_constraint("ck_factor_scope_2_method", "emission_factors", type_="check")
    op.drop_column("calculation_runs", "total_market_based_kgco2e")
    op.drop_column("calculation_runs", "total_location_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_market_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_location_based_kgco2e")
    op.drop_column("inventories", "scope_2_primary_method")
    op.drop_column("activity_records", "scope_2_method")
    op.drop_column("emission_factors", "scope_2_method")
