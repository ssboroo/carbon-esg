"""Add immutable, tenant-scoped human review decisions for emission factors."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_emission_factor_reviews"
down_revision = "0002_append_only_audit_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "emission_factors",
        sa.Column("submitted_by_subject", sa.String(255), nullable=True),
    )
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
    op.execute("ALTER TABLE emission_factor_reviews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE emission_factor_reviews FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON emission_factor_reviews
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        WITH CHECK (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )
    op.execute(
        "CREATE POLICY emission_factor_reviews_no_update ON emission_factor_reviews "
        "AS RESTRICTIVE FOR UPDATE USING (false) WITH CHECK (false)"
    )
    op.execute(
        "CREATE POLICY emission_factor_reviews_no_delete ON emission_factor_reviews "
        "AS RESTRICTIVE FOR DELETE USING (false)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS emission_factor_reviews_no_update ON emission_factor_reviews")
    op.execute("DROP POLICY IF EXISTS emission_factor_reviews_no_delete ON emission_factor_reviews")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON emission_factor_reviews")
    op.drop_index("ix_factor_reviews_org_decision", table_name="emission_factor_reviews")
    op.drop_table("emission_factor_reviews")
    op.drop_column("emission_factors", "submitted_by_subject")
