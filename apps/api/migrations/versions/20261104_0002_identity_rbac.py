"""Add stable OIDC identity mapping and constrained organization roles.

The initial enterprise migration creates tables from current SQLAlchemy metadata.
These guards also support databases where that migration was applied before the
identity columns were added to the model.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0002"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "auth_issuer" not in columns:
        op.add_column("users", sa.Column("auth_issuer", sa.String(length=500), nullable=True))
    if "auth_subject" not in columns:
        op.add_column("users", sa.Column("auth_subject", sa.String(length=255), nullable=True))

    unique_constraints = {
        item["name"] for item in sa.inspect(bind).get_unique_constraints("users")
    }
    if "uq_user_oidc_identity" not in unique_constraints:
        op.create_unique_constraint(
            "uq_user_oidc_identity", "users", ["auth_issuer", "auth_subject"]
        )

    checks = {
        item["name"] for item in sa.inspect(bind).get_check_constraints("memberships")
    }
    if "ck_membership_role_allowed" not in checks:
        op.create_check_constraint(
            "ck_membership_role_allowed",
            "memberships",
            "role IN ('owner', 'admin', 'manager', 'reviewer', 'viewer')",
        )


def downgrade():
    bind = op.get_bind()
    checks = {
        item["name"] for item in sa.inspect(bind).get_check_constraints("memberships")
    }
    if "ck_membership_role_allowed" in checks:
        op.drop_constraint("ck_membership_role_allowed", "memberships", type_="check")
    unique_constraints = {
        item["name"] for item in sa.inspect(bind).get_unique_constraints("users")
    }
    if "uq_user_oidc_identity" in unique_constraints:
        op.drop_constraint("uq_user_oidc_identity", "users", type_="unique")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "auth_subject" in columns:
        op.drop_column("users", "auth_subject")
    if "auth_issuer" in columns:
        op.drop_column("users", "auth_issuer")
