"""Enforce tenant RLS on organization memberships.

Membership rows are tenant-scoped authorization data and must not be readable
across organizations, even when queries run under a non-owner application role.
"""
from alembic import op

revision = "20261104_0003"
down_revision = "20261104_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE "memberships" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "memberships" FORCE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation ON memberships
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))
    """)


def downgrade():
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON memberships')
    op.execute('ALTER TABLE "memberships" DISABLE ROW LEVEL SECURITY')
