"""Bring the tenant schema in line with the current SQLAlchemy models.

Revision ID: 0002_scope2_reviews_evidence
Revises: 0001_tenant_esg_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_scope2_reviews_evidence"
down_revision = "0001_tenant_esg_schema"
branch_labels = None
depends_on = None


def _enable_tenant_rls(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(
        f"CREATE POLICY tenant_isolation ON {table} "
        "USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid) "
        "WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)"
    ))


def upgrade() -> None:
    # Scope 2 method metadata was added to the ORM after the original schema
    # migration. Keep legacy Scope 1 and existing Scope 2 rows readable.
    op.add_column("emission_factors", sa.Column("scope_2_method", sa.String(24), nullable=True))
    op.add_column("emission_factors", sa.Column("submitted_by_subject", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_factor_scope_2_method",
        "emission_factors",
        "((scope = 'scope_1' AND scope_2_method IS NULL) OR "
        "(scope = 'scope_2' AND (scope_2_method IS NULL OR scope_2_method IN ('location_based', 'market_based'))))",
    )

    op.add_column(
        "inventories",
        sa.Column("scope_2_primary_method", sa.String(24), server_default="location_based", nullable=False),
    )
    op.create_check_constraint(
        "ck_inventory_scope_2_primary_method",
        "inventories",
        "scope_2_primary_method IN ('location_based', 'market_based')",
    )

    op.add_column("activity_records", sa.Column("scope_2_method", sa.String(24), nullable=True))
    op.create_check_constraint(
        "ck_activity_scope_2_method",
        "activity_records",
        "((scope = 'scope_1' AND scope_2_method IS NULL) OR "
        "(scope = 'scope_2' AND (scope_2_method IS NULL OR scope_2_method IN ('location_based', 'market_based'))))",
    )

    op.add_column(
        "calculation_runs",
        sa.Column("scope_2_primary_method", sa.String(24), server_default="location_based", nullable=False),
    )
    op.add_column("calculation_runs", sa.Column("scope_2_location_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("scope_2_market_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("total_location_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.add_column("calculation_runs", sa.Column("total_market_based_kgco2e", sa.Numeric(24, 8), nullable=True))
    op.create_check_constraint(
        "ck_calculation_scope_2_primary_method",
        "calculation_runs",
        "scope_2_primary_method IN ('location_based', 'market_based')",
    )

    # One immutable human decision per immutable factor version.
    op.create_table(
        "emission_factor_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("emission_factor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reviewer_subject", sa.String(255), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "emission_factor_id"],
            ["emission_factors.organization_id", "emission_factors.id"],
            ondelete="RESTRICT",
            name="fk_factor_review_factor_tenant",
        ),
        sa.UniqueConstraint("organization_id", "emission_factor_id", name="uq_factor_review_org_factor"),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_factor_review_decision"),
        sa.CheckConstraint("length(btrim(review_note)) >= 10", name="ck_factor_review_note"),
    )
    op.create_index(
        "ix_factor_reviews_org_decision",
        "emission_factor_reviews",
        ["organization_id", "decision", "reviewed_at"],
    )

    # Evidence metadata is tenant-scoped; bytes remain in a private S3-compatible bucket.
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activity_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_by_subject", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(180), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("scan_status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("storage_key", name="uq_evidence_storage_key"),
        sa.UniqueConstraint("organization_id", "id", name="uq_evidence_org_id"),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 15728640", name="ck_evidence_size"),
        sa.CheckConstraint("scan_status = 'clean'", name="ck_evidence_clean_only"),
    )
    op.create_index("ix_evidence_org_created", "evidence", ["organization_id", "created_at"])
    op.create_index("ix_evidence_org_activity", "evidence", ["organization_id", "activity_id"])

    _enable_tenant_rls("emission_factor_reviews")
    _enable_tenant_rls("evidence")

    # Calculation history, review decisions, evidence metadata and audit events
    # are append-only. Corrections are represented by new records/versions.
    op.execute("""
        CREATE FUNCTION prevent_append_only_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only; UPDATE and DELETE are prohibited', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table, trigger in (
        ("calculation_runs", "calculation_runs_append_only"),
        ("emission_factor_reviews", "emission_factor_reviews_append_only"),
        ("evidence", "evidence_append_only"),
        ("audit_events", "audit_events_append_only"),
    ):
        op.execute(sa.text(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation()"
        ))


def downgrade() -> None:
    for table, trigger in (
        ("audit_events", "audit_events_append_only"),
        ("evidence", "evidence_append_only"),
        ("emission_factor_reviews", "emission_factor_reviews_append_only"),
        ("calculation_runs", "calculation_runs_append_only"),
    ):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
    op.execute("DROP FUNCTION IF EXISTS prevent_append_only_mutation()")

    for table in ("evidence", "emission_factor_reviews"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.drop_table("evidence")
    op.drop_index("ix_factor_reviews_org_decision", table_name="emission_factor_reviews")
    op.drop_table("emission_factor_reviews")

    op.drop_constraint("ck_calculation_scope_2_primary_method", "calculation_runs", type_="check")
    op.drop_column("calculation_runs", "total_market_based_kgco2e")
    op.drop_column("calculation_runs", "total_location_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_market_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_location_based_kgco2e")
    op.drop_column("calculation_runs", "scope_2_primary_method")

    op.drop_constraint("ck_activity_scope_2_method", "activity_records", type_="check")
    op.drop_column("activity_records", "scope_2_method")

    op.drop_constraint("ck_inventory_scope_2_primary_method", "inventories", type_="check")
    op.drop_column("inventories", "scope_2_primary_method")

    op.drop_constraint("ck_factor_scope_2_method", "emission_factors", type_="check")
    op.drop_column("emission_factors", "submitted_by_subject")
    op.drop_column("emission_factors", "scope_2_method")
