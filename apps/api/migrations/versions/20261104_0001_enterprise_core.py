"""Initial enterprise ESG data model with tenant row-level security."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261104_0001"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "memberships", "emission_factors", "activity_records", "evidence",
    "calculation_snapshots", "audit_events",
)


def upgrade():
    # Tables are generated from the shared SQLAlchemy metadata.
    from app.models import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # RLS is a second enforcement layer. Application authorization remains mandatory.
    for table in TENANT_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(
            f'''CREATE POLICY tenant_isolation ON "{table}"
            USING (tenant_id::text = current_setting('app.current_tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))'''
        ))

    # Audit events are append-only for the application role.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER audit_events_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_update_delete ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation()")
    for table in reversed(TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    from app.models import Base
    Base.metadata.drop_all(bind=op.get_bind())
