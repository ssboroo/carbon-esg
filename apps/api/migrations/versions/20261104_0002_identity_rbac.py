"""Add stable OIDC identity mapping and constrained organization roles."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0002"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("auth_issuer", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("auth_subject", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_user_oidc_identity", "users", ["auth_issuer", "auth_subject"]
    )
    op.create_check_constraint(
        "ck_membership_role_allowed",
        "memberships",
        "role IN ('owner', 'admin', 'manager', 'reviewer', 'viewer')",
    )


def downgrade():
    op.drop_constraint("ck_membership_role_allowed", "memberships", type_="check")
    op.drop_constraint("uq_user_oidc_identity", "users", type_="unique")
    op.drop_column("users", "auth_subject")
    op.drop_column("users", "auth_issuer")
