"""Add immutable tenant-scoped evidence metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_evidence_vault"
down_revision = "0003_emission_factor_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activity_records.id", ondelete="SET NULL")),
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
    op.execute("ALTER TABLE evidence ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE evidence FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON evidence
        USING (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
        WITH CHECK (organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid)
    """)
    op.execute(
        "CREATE POLICY evidence_no_update ON evidence "
        "AS RESTRICTIVE FOR UPDATE USING (false) WITH CHECK (false)"
    )
    op.execute(
        "CREATE POLICY evidence_no_delete ON evidence "
        "AS RESTRICTIVE FOR DELETE USING (false)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS evidence_no_update ON evidence")
    op.execute("DROP POLICY IF EXISTS evidence_no_delete ON evidence")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON evidence")
    op.drop_index("ix_evidence_org_activity", table_name="evidence")
    op.drop_index("ix_evidence_org_created", table_name="evidence")
    op.drop_table("evidence")
