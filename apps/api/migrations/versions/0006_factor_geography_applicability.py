"""Add explicit factor geography and applicability dates.

Legacy rows are retained for historical snapshots but are marked as geographically
unspecified and are excluded from new activity entry and recalculation.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_factor_geo_validity"
down_revision = "0005_scope2_methods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "emission_factors",
        sa.Column("geography_code", sa.String(32), nullable=False, server_default="LEGACY_UNSPECIFIED"),
    )
    op.add_column(
        "emission_factors",
        sa.Column("geography_name", sa.String(160), nullable=False, server_default="Legacy — geographic scope not recorded"),
    )
    op.add_column(
        "emission_factors",
        sa.Column("geography_boundary", sa.String(24), nullable=False, server_default="other"),
    )
    # Legacy factors have no evidence-backed validity dates; preserve that unknown as NULL.
    op.add_column("emission_factors", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("emission_factors", sa.Column("valid_to", sa.Date(), nullable=True))
    op.alter_column("emission_factors", "geography_code", server_default=None)
    op.alter_column("emission_factors", "geography_name", server_default=None)
    op.alter_column("emission_factors", "geography_boundary", server_default=None)
    op.create_check_constraint(
        "ck_factor_geography_boundary",
        "emission_factors",
        "geography_boundary IN ('global', 'national', 'subnational', 'grid', 'market', 'facility', 'other')",
    )
    op.create_check_constraint(
        "ck_factor_geography_code",
        "emission_factors",
        "geography_code ~ '^[A-Z0-9][A-Z0-9._:-]{0,31}$'",
    )
    op.create_check_constraint(
        "ck_factor_geography_name",
        "emission_factors",
        "length(btrim(geography_name)) > 0",
    )
    op.create_check_constraint(
        "ck_factor_validity_period",
        "emission_factors",
        "((valid_from IS NULL AND valid_to IS NULL) OR (valid_from IS NOT NULL AND valid_to IS NOT NULL AND valid_from <= valid_to))",
    )
    op.create_index(
        "ix_factors_org_geography",
        "emission_factors",
        ["organization_id", "geography_code", "valid_from", "valid_to"],
    )

    op.add_column(
        "activity_records",
        sa.Column("activity_geography_code", sa.String(32), nullable=False, server_default="LEGACY_UNSPECIFIED"),
    )
    op.add_column(
        "activity_records",
        sa.Column("activity_geography_name", sa.String(160), nullable=False, server_default="Legacy — geographic scope not recorded"),
    )
    op.alter_column("activity_records", "activity_geography_code", server_default=None)
    op.alter_column("activity_records", "activity_geography_name", server_default=None)
    op.create_check_constraint(
        "ck_activity_geography_code",
        "activity_records",
        "activity_geography_code ~ '^[A-Z0-9][A-Z0-9._:-]{0,31}$'",
    )
    op.create_check_constraint(
        "ck_activity_geography_name",
        "activity_records",
        "length(btrim(activity_geography_name)) > 0",
    )
    op.create_index(
        "ix_activity_org_geography",
        "activity_records",
        ["organization_id", "activity_geography_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_org_geography", table_name="activity_records")
    op.drop_constraint("ck_activity_geography_name", "activity_records", type_="check")
    op.drop_constraint("ck_activity_geography_code", "activity_records", type_="check")
    op.drop_column("activity_records", "activity_geography_name")
    op.drop_column("activity_records", "activity_geography_code")
    op.drop_index("ix_factors_org_geography", table_name="emission_factors")
    op.drop_constraint("ck_factor_validity_period", "emission_factors", type_="check")
    op.drop_constraint("ck_factor_geography_name", "emission_factors", type_="check")
    op.drop_constraint("ck_factor_geography_code", "emission_factors", type_="check")
    op.drop_constraint("ck_factor_geography_boundary", "emission_factors", type_="check")
    op.drop_column("emission_factors", "valid_to")
    op.drop_column("emission_factors", "valid_from")
    op.drop_column("emission_factors", "geography_boundary")
    op.drop_column("emission_factors", "geography_name")
    op.drop_column("emission_factors", "geography_code")
