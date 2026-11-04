"""Make calculation snapshots append-only at the database layer."""
from alembic import op

revision = "20261104_0004"
down_revision = "20261104_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_calculation_snapshot_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'calculation_snapshots are immutable; create a new snapshot';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER calculation_snapshots_no_update_delete
        BEFORE UPDATE OR DELETE ON calculation_snapshots
        FOR EACH ROW EXECUTE FUNCTION prevent_calculation_snapshot_mutation();
    """)


def downgrade():
    op.execute(
        "DROP TRIGGER IF EXISTS calculation_snapshots_no_update_delete ON calculation_snapshots"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_calculation_snapshot_mutation()")
