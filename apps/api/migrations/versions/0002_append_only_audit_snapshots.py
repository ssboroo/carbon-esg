"""Make calculation snapshots and audit events append-only with restrictive RLS policies."""

from alembic import op

revision = "0002_append_only_audit_snapshots"
down_revision = "0001_tenant_esg_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("calculation_runs", "audit_events"):
        op.execute(
            f"CREATE POLICY {table}_no_update ON {table} "
            "AS RESTRICTIVE FOR UPDATE USING (false) WITH CHECK (false)"
        )
        op.execute(
            f"CREATE POLICY {table}_no_delete ON {table} "
            "AS RESTRICTIVE FOR DELETE USING (false)"
        )


def downgrade() -> None:
    for table in ("calculation_runs", "audit_events"):
        op.execute(f"DROP POLICY IF EXISTS {table}_no_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_no_delete ON {table}")
