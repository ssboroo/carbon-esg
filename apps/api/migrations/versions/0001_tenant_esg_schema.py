"""Initial tenant-scoped ESG persistence schema.

Revision ID: 0001_tenant_esg_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_tenant_esg_schema"
down_revision = None
branch_labels = None
depends_on = None


def _rls(table: str, tenant_column: str = "organization_id") -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING ({tenant_column} = NULLIF(current_setting('app.current_organization_id', true), '')::uuid) "
        f"WITH CHECK ({tenant_column} = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)"
    ))


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_subject", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_subject", name="uq_membership_org_subject"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'editor', 'viewer')", name="ck_membership_role"),
    )
    op.create_index("ix_memberships_subject", "organization_memberships", ["user_subject"])
    op.create_table(
        "emission_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("factor_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("factor_value", sa.Numeric(24, 12), nullable=False),
        sa.Column("factor_unit", sa.String(32), nullable=False),
        sa.Column("gas_basis", sa.String(24), nullable=False, server_default="CO2e"),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_document", sa.String(255)),
        sa.Column("factor_year", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "factor_code", "version", name="uq_factor_org_code_version"),
        sa.UniqueConstraint("organization_id", "id", name="uq_factor_org_id"),
        sa.CheckConstraint("factor_value >= 0", name="ck_factor_nonnegative"),
        sa.CheckConstraint("factor_year BETWEEN 1900 AND 2200", name="ck_factor_year"),
        sa.CheckConstraint("source_url LIKE 'https://%'", name="ck_factor_https_source"),
        sa.CheckConstraint("scope IN ('scope_1', 'scope_2')", name="ck_factor_scope"),
    )
    op.create_index("ix_factors_org_scope_category", "emission_factors", ["organization_id", "scope", "category"])
    op.create_table(
        "inventories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by_subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_inventory_org_id"),
        sa.CheckConstraint("reporting_period_end >= reporting_period_start", name="ck_inventory_period"),
        sa.CheckConstraint("status IN ('draft', 'review', 'approved')", name="ck_inventory_status"),
    )
    op.create_index("ix_inventories_org_period", "inventories", ["organization_id", "reporting_period_start", "reporting_period_end"])
    op.create_table(
        "activity_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("emission_factor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("activity_amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("activity_unit", sa.String(32), nullable=False),
        sa.Column("factor_value_snapshot", sa.Numeric(24, 12), nullable=False),
        sa.Column("factor_unit_snapshot", sa.String(32), nullable=False),
        sa.Column("emissions_kgco2e", sa.Numeric(24, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "inventory_id"], ["inventories.organization_id", "inventories.id"], ondelete="CASCADE", name="fk_activity_inventory_tenant"),
        sa.ForeignKeyConstraint(["organization_id", "emission_factor_id"], ["emission_factors.organization_id", "emission_factors.id"], name="fk_activity_factor_tenant"),
        sa.CheckConstraint("activity_amount > 0", name="ck_activity_amount_positive"),
        sa.CheckConstraint("factor_value_snapshot >= 0 AND emissions_kgco2e >= 0", name="ck_activity_emissions_nonnegative"),
        sa.CheckConstraint("activity_unit = factor_unit_snapshot", name="ck_activity_units_match"),
        sa.CheckConstraint("scope IN ('scope_1', 'scope_2')", name="ck_activity_scope"),
    )
    op.create_index("ix_activity_org_inventory", "activity_records", ["organization_id", "inventory_id"])
    op.create_table(
        "calculation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_1_kgco2e", sa.Numeric(24, 8), nullable=False),
        sa.Column("scope_2_kgco2e", sa.Numeric(24, 8), nullable=False),
        sa.Column("total_kgco2e", sa.Numeric(24, 8), nullable=False),
        sa.Column("methodology_version", sa.String(80), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("calculated_by_subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "inventory_id"], ["inventories.organization_id", "inventories.id"], ondelete="CASCADE", name="fk_calculation_inventory_tenant"),
        sa.CheckConstraint("scope_1_kgco2e >= 0 AND scope_2_kgco2e >= 0", name="ck_calculation_scopes_nonnegative"),
        sa.CheckConstraint("total_kgco2e = scope_1_kgco2e + scope_2_kgco2e", name="ck_calculation_total_matches_scopes"),
    )
    op.create_index("ix_calculation_org_inventory_created", "calculation_runs", ["organization_id", "inventory_id", "created_at"])
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_subject", sa.String(255), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_org_created", "audit_events", ["organization_id", "created_at"])
    op.create_index("ix_audit_org_entity", "audit_events", ["organization_id", "entity_type", "entity_id"])

    # Every tenant-owned table is protected even if a query accidentally omits its tenant filter.
    _rls("organizations", "id")
    for table in ("emission_factors", "inventories", "activity_records", "calculation_runs", "audit_events"):
        _rls(table)

    # Users must be able to discover their own memberships before a tenant is selected.
    op.execute("ALTER TABLE organization_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_memberships FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY membership_self_or_tenant ON organization_memberships
        USING (
            user_subject = NULLIF(current_setting('app.current_user_subject', true), '')
            OR organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        WITH CHECK (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
    """)

    # Factor records are versioned, not edited in place. Add a new version for corrections.
    op.execute("""CREATE FUNCTION prevent_emission_factor_mutation() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'Emission factors are immutable; insert a new version'; END;
    $$ LANGUAGE plpgsql""")
    op.execute("CREATE TRIGGER emission_factors_immutable BEFORE UPDATE OR DELETE ON emission_factors FOR EACH ROW EXECUTE FUNCTION prevent_emission_factor_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS emission_factors_immutable ON emission_factors")
    op.execute("DROP FUNCTION IF EXISTS prevent_emission_factor_mutation()")
    for table in ("audit_events", "calculation_runs", "activity_records", "inventories", "emission_factors", "organization_memberships"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.drop_table(table)
    op.drop_table("organizations")
