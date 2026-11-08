"""Add separate location-based and market-based Scope 2 accounting outputs."""

from alembic import op
import sqlalchemy as sa

revision = "0005_scope2_methods"
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
    op.add_column("calculation_runs", sa.Column("scope_2_primary_method", sa.String(24), nullable=False, server_default="location_based"))
    op.add_column("calculation_runs", sa.Column("scope_2_location_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("scope_2_market_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("total_location_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("total_market_based_kgco2e", sa.Numeric(24, 8), nullable=True))

    # Preserve old unclassified Scope 2 records without guessing their basis.
    op.execute("UPDATE emission_factors SET scope_2_method = 'legacy_unclassified' WHERE scope = 'scope_2' AND scope_2_method IS NULL")
    op.execute("UPDATE activity_records SET scope_2_method = 'legacy_unclassified' WHERE scope = 'scope_2' AND scope_2_method IS NULL")

    op.create_check_constraint(
        "ck_factor_scope_2_method",
        "emission_factors",
        "((scope = 'scope_1' AND scope_2_method IS NULL) OR "
        "(scope = 'scope_2' AND scope_2_method IN ('location_based', 'market_based', 'legacy_unclassified')))",
    )
    op.create_check_constraint(
        "ck_activity_scope_2_method",
        "activity_records",
        "((scope = 'scope_1' AND scope_2_method IS NULL) OR "
        "(scope = 'scope_2' AND scope_2_method IN ('location_based', 'market_based', 'legacy_unclassified')))",
    )
    op.create_check_constraint(
        "ck_inventory_scope_2_primary_method",
        "inventories",
        "scope_2_primary_method IN ('location_based', 'market_based')",
    )
    op.create_check_constraint(
        "ck_calculation_scope_2_primary_method",
        "calculation_runs",
        "scope_2_primary_method IN ('location_based', 'market_based')",
    )
    # New Scope 2 rows must be classified by method; legacy rows remain read-only.
    op.execute(
        "CREATE POLICY emission_factors_scope2_method_insert ON emission_factors "
        "AS RESTRICTIVE FOR INSERT WITH CHECK "
        "(scope <> 'scope_2' OR scope_2_method IN ('location_based', 'market_based'))"
    )
    op.execute(
        "CREATE POLICY activity_records_scope2_method_insert ON activity_records "
        "AS RESTRICTIVE FOR INSERT WITH CHECK "
        "(scope <> 'scope_2' OR scope_2_method IN ('location_based', 'market_based'))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS activity_records_scope2_method_insert ON activity_records")
    op.execute("DROP POLICY IF EXISTS emission_factors_scope2_method_insert ON emission_factors")
    op.drop_constraint("ck_calculation_scope_2_primary_method", "calculation_runs", type_="check")
    op.drop_constraint("ck_inventory_scope_2_primary_method", "inventories", type_="check")
    op.drop_constraint("ck_activity_scope_2_method", "activity_records", type_="check")
    op.drop_constraint("ck_factor_scope_2_method", "emission_factors", type_="check")
    op.drop_column("calculation_runs", "total_market_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_primary_method")
    op.drop_column("calculation_runs", "total_location_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_market_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_location_based_kgco2e")
    op.drop_column("inventories", "scope_2_primary_method")
    op.drop_column("activity_records", "scope_2_method")
    op.drop_column("emission_factors", "scope_2_method")
