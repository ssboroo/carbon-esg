"""Make calculation snapshots and audit events append-only.

Revision ID: 0002_append_only_audit_snapshots
Revises: 0001_tenant_esg_schema
"""
from alembic import op

revision = "0002_append_only_audit_snapshots"
down_revision = "0001_tenant_esg_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION reject_append_only_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only; create a new event or calculation run',
                TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER calculation_runs_append_only
        BEFORE UPDATE OR DELETE ON calculation_runs
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS calculation_runs_append_only ON calculation_runs")
    op.execute("DROP FUNCTION IF EXISTS reject_append_only_mutation()")
