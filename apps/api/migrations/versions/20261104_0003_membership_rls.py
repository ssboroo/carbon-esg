"""Reassert tenant RLS policy on organization memberships.

The initial enterprise migration already creates this policy. This revision
keeps the security invariant explicit and safely repairs a missing or stale
policy without weakening the previous migration on downgrade.
"""
from alembic import op

revision = "20261104_0003"
down_revision = "20261104_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE "memberships" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "memberships" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON memberships')
    op.execute("""
        CREATE POLICY tenant_isolation ON memberships
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))
    """)


def downgrade():
    # Revision 0001 already enabled forced RLS and created this policy.
    # Keep that baseline protection intact when rolling back this revision.
    op.execute('ALTER TABLE "memberships" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "memberships" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON memberships')
    op.execute("""
        CREATE POLICY tenant_isolation ON memberships
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))
    """)
