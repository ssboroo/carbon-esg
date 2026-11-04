"""Require reviewer evidence even for direct approved-factor inserts."""
from alembic import op

revision = "20261104_0007"
down_revision = "20261104_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION guard_approved_emission_factor()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.approval_status = 'approved'
               AND (
                 NEW.approved_by IS NULL
                 OR NEW.approved_at IS NULL
                 OR NEW.approval_note IS NULL
                 OR length(trim(NEW.approval_note)) < 10
               ) THEN
              RAISE EXCEPTION 'approved factor insert requires reviewer, timestamp and substantive note';
            END IF;
            RETURN NEW;
          END IF;

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
    op.execute("DROP TRIGGER IF EXISTS emission_factors_approval_guard ON emission_factors")
    op.execute("""
        CREATE TRIGGER emission_factors_approval_guard
        BEFORE INSERT OR UPDATE OR DELETE ON emission_factors
        FOR EACH ROW EXECUTE FUNCTION guard_approved_emission_factor()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS emission_factors_approval_guard ON emission_factors")
    op.execute("DROP FUNCTION IF EXISTS guard_approved_emission_factor()")
