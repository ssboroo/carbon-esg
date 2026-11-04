"""Add Scope 3 category materiality assessments and expand activity scope check."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261104_0011"
down_revision = "20261104_0010"
branch_labels = None
depends_on = None

SCOPE3_CATEGORIES = (
    "purchased_goods_and_services",
    "capital_goods",
    "fuel_and_energy_related_activities",
    "upstream_transportation_and_distribution",
    "waste_generated_in_operations",
    "business_travel",
    "employee_commuting",
    "upstream_leased_assets",
    "downstream_transportation_and_distribution",
    "processing_of_sold_products",
    "use_of_sold_products",
    "end_of_life_treatment_of_sold_products",
    "downstream_leased_assets",
    "franchises",
    "investments",
)


def upgrade():
    op.drop_constraint("ck_activity_scope", "activity_records", type_="check")
    op.create_check_constraint(
        "ck_activity_scope",
        "activity_records",
        "scope IN ('scope_1', 'scope_2', 'scope_3')",
    )
    op.create_table(
        "scope3_category_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporting_year", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("applicability", sa.String(length=24), nullable=False, server_default="not_assessed"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "reporting_year", "category", name="uq_scope3_assessment_tenant_year_category"),
        sa.CheckConstraint(
            "category IN (" + ", ".join("'" + item + "'" for item in SCOPE3_CATEGORIES) + ")",
            name="ck_scope3_assessment_category",
        ),
        sa.CheckConstraint(
            "applicability IN ('not_assessed', 'relevant', 'not_relevant')",
            name="ck_scope3_assessment_applicability",
        ),
        sa.CheckConstraint(
            "applicability <> 'not_relevant' OR (rationale IS NOT NULL AND length(trim(rationale)) >= 20)",
            name="ck_scope3_assessment_exclusion_rationale",
        ),
        sa.CheckConstraint(
            "applicability = 'not_assessed' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_scope3_assessment_reviewer",
        ),
        sa.CheckConstraint("reporting_year BETWEEN 1900 AND 2200", name="ck_scope3_assessment_year"),
    )
    op.create_index(
        "ix_scope3_assessment_tenant_year",
        "scope3_category_assessments",
        ["tenant_id", "reporting_year"],
    )
    op.execute("ALTER TABLE scope3_category_assessments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scope3_category_assessments FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON scope3_category_assessments
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))
    """)


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON scope3_category_assessments")
    op.execute("ALTER TABLE scope3_category_assessments DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_scope3_assessment_tenant_year", table_name="scope3_category_assessments")
    op.drop_table("scope3_category_assessments")
    op.drop_constraint("ck_activity_scope", "activity_records", type_="check")
    op.create_check_constraint(
        "ck_activity_scope",
        "activity_records",
        "scope IN ('scope_1', 'scope_2')",
    )
