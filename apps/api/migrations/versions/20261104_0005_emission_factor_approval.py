"""Add governed human approval to tenant emission factors."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0005"
down_revision = "20261104_0004"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("emission_factors")
    }
    if "approved_at" not in columns:
        op.add_column(
            "emission_factors",
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "approval_note" not in columns:
        op.add_column(
            "emission_factors",
            sa.Column("approval_note", sa.Text(), nullable=True),
        )
    op.execute("""
        CREATE OR REPLACE FUNCTION guard_approved_emission_factor()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            IF OLD.approval_status = 'approved' THEN
              RAISE EXCEPTION 'approved emission factors are immutable; submit a new version';
            END IF;
            RETURN OLD;
          END IF;

          IF OLD.approval_status = 'approved' THEN
            RAISE EXCEPTION 'approved emission factors are immutable; submit a new version';
          END IF;

          IF NEW.approval_status = 'approved' THEN
            IF OLD.approval_status <> 'pending'
               OR NEW.approved_by IS NULL
               OR NEW.approved_at IS NULL
               OR NEW.approval_note IS NULL
               OR length(trim(NEW.approval_note)) < 10 THEN
              RAISE EXCEPTION 'approval requires a pending factor, reviewer, timestamp and substantive note';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER emission_factors_approval_guard
        BEFORE UPDATE OR DELETE ON emission_factors
        FOR EACH ROW EXECUTE FUNCTION guard_approved_emission_factor();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS emission_factors_approval_guard ON emission_factors")
    op.execute("DROP FUNCTION IF EXISTS guard_approved_emission_factor()")
    op.drop_column("emission_factors", "approval_note")
    op.drop_column("emission_factors", "approved_at")
