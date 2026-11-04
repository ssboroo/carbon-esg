"""PostgreSQL migration and tenant-isolation tests run against a real PostgreSQL service."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="PostgreSQL integration DB is not configured")

TENANT_TABLES = (
    "tenants",
    "memberships",
    "emission_factors",
    "activity_records",
    "evidence",
    "calculation_snapshots",
    "audit_events",
)


def test_all_enterprise_tables_exist_and_rls_is_forced():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            for table in TENANT_TABLES:
                row = connection.execute(
                    text("""
                        SELECT c.relrowsecurity, c.relforcerowsecurity
                        FROM pg_class c
                        WHERE c.oid = to_regclass(:table_name)
                    """),
                    {"table_name": f"public.{table}"},
                ).one_or_none()
                assert row is not None, f"missing table: {table}"
                assert row.relrowsecurity, f"RLS is not enabled on {table}"
                assert row.relforcerowsecurity, f"RLS is not forced on {table}"

                policy = connection.execute(
                    text("""
                        SELECT count(*) FROM pg_policies
                        WHERE schemaname = 'public' AND tablename = :table_name
                          AND policyname = 'tenant_isolation'
                    """),
                    {"table_name": table},
                ).scalar_one()
                assert policy == 1, f"tenant isolation policy missing on {table}"
    finally:
        engine.dispose()


def test_non_owner_role_cannot_read_another_tenants_rows():
    """Exercise forced RLS as a non-owner, non-superuser, NOBYPASSRLS role."""
    engine = create_engine(DATABASE_URL)
    tenant_a, tenant_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()

    try:
        with engine.begin() as connection:
            connection.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_esg_rls_test') THEN
                        CREATE ROLE carbon_esg_rls_test NOLOGIN NOINHERIT NOBYPASSRLS;
                    END IF;
                END
                $$;
            """))
            connection.execute(text(
                "ALTER ROLE carbon_esg_rls_test NOLOGIN NOINHERIT NOBYPASSRLS"
            ))
            connection.execute(text(
                "GRANT USAGE ON SCHEMA public TO carbon_esg_rls_test"
            ))
            connection.execute(text(
                "GRANT SELECT ON tenants, memberships TO carbon_esg_rls_test"
            ))

            connection.execute(text("""
                INSERT INTO tenants (id, legal_name, country_code)
                VALUES (:tenant_a, 'RLS Test Tenant A', 'MN'),
                       (:tenant_b, 'RLS Test Tenant B', 'MN')
            """), {"tenant_a": tenant_a, "tenant_b": tenant_b})
            connection.execute(text("""
                INSERT INTO users (id, email, display_name, is_active)
                VALUES (:user_a, :email_a, 'RLS Test User A', true),
                       (:user_b, :email_b, 'RLS Test User B', true)
            """), {
                "user_a": user_a,
                "email_a": f"{user_a}@rls-test.invalid",
                "user_b": user_b,
                "email_b": f"{user_b}@rls-test.invalid",
            })
            connection.execute(text("""
                INSERT INTO memberships (id, tenant_id, user_id, role)
                VALUES (:membership_a, :tenant_a, :user_a, 'viewer'),
                       (:membership_b, :tenant_b, :user_b, 'admin')
            """), {
                "membership_a": uuid4(),
                "tenant_a": tenant_a,
                "user_a": user_a,
                "membership_b": uuid4(),
                "tenant_b": tenant_b,
                "user_b": user_b,
            })

        with engine.begin() as connection:
            role = connection.execute(text("""
                SELECT rolsuper, rolbypassrls
                FROM pg_roles WHERE rolname = 'carbon_esg_rls_test'
            """)).one()
            assert role.rolsuper is False
            assert role.rolbypassrls is False

            connection.execute(text("SET LOCAL ROLE carbon_esg_rls_test"))
            # No tenant context must fail closed.
            assert connection.execute(
                text("SELECT count(*) FROM memberships")
            ).scalar_one() == 0

            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_a)},
            )
            visible_a = connection.execute(
                text("SELECT tenant_id, role FROM memberships")
            ).all()
            assert [(row.tenant_id, row.role) for row in visible_a] == [(tenant_a, "viewer")]
            visible_tenant_a = connection.execute(
                text("SELECT id FROM tenants")
            ).scalars().all()
            assert visible_tenant_a == [tenant_a]

            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_b)},
            )
            visible_b = connection.execute(
                text("SELECT tenant_id, role FROM memberships")
            ).all()
            assert [(row.tenant_id, row.role) for row in visible_b] == [(tenant_b, "admin")]
            visible_tenant_b = connection.execute(
                text("SELECT id FROM tenants")
            ).scalars().all()
            assert visible_tenant_b == [tenant_b]
    finally:
        engine.dispose()


def test_audit_events_have_append_only_trigger():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            trigger = connection.execute(
                text("""
                    SELECT count(*) FROM pg_trigger
                    WHERE tgrelid = 'public.audit_events'::regclass
                      AND tgname = 'audit_events_no_update_delete'
                      AND NOT tgisinternal AND tgenabled <> 'D'
                """)
            ).scalar_one()
            assert trigger == 1
    finally:
        engine.dispose()



def test_calculation_snapshots_have_append_only_trigger():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            trigger = connection.execute(
                text("""
                    SELECT count(*) FROM pg_trigger
                    WHERE tgrelid = 'public.calculation_snapshots'::regclass
                      AND tgname = 'calculation_snapshots_no_update_delete'
                      AND NOT tgisinternal AND tgenabled <> 'D'
                """)
            ).scalar_one()
            assert trigger == 1
    finally:
        engine.dispose()


def test_alembic_revision_is_applied():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert revision == "20261104_0006"
    finally:
        engine.dispose()



def test_approved_emission_factors_have_database_guard():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            trigger = connection.execute(
                text("""
                    SELECT count(*) FROM pg_trigger
                    WHERE tgrelid = 'public.emission_factors'::regclass
                      AND tgname = 'emission_factors_approval_guard'
                      AND NOT tgisinternal AND tgenabled <> 'D'
                """)
            ).scalar_one()
            assert trigger == 1
            columns = {
                row.column_name
                for row in connection.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'emission_factors'
                """))
            }
            assert {"approved_at", "approval_note"}.issubset(columns)
    finally:
        engine.dispose()
