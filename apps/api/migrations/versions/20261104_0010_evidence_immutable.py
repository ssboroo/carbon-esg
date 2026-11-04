"""Make evidence metadata append-only."""
from alembic import op

revision = "20261104_0010"
down_revision = "20261104_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_evidence_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'evidence metadata is immutable; upload a new evidence version';
        END;
        $$;
    """)
    op.execute("DROP TRIGGER IF EXISTS evidence_no_update_delete ON evidence")
    op.execute("""
        CREATE TRIGGER evidence_no_update_delete
        BEFORE UPDATE OR DELETE ON evidence
        FOR EACH ROW EXECUTE FUNCTION prevent_evidence_mutation()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS evidence_no_update_delete ON evidence")
    op.execute("DROP FUNCTION IF EXISTS prevent_evidence_mutation()")
