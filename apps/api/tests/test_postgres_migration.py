"""PostgreSQL migration and tenant-isolation tests run against a real PostgreSQL service."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL")
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


def test_runtime_role_is_non_owner_and_rls_isolation_covers_every_tenant_table():
    """Verify the actual application DB role cannot bypass forced RLS."""
    if not MIGRATION_DATABASE_URL:
        pytest.skip("MIGRATION_DATABASE_URL is required to seed cross-tenant fixtures")

    engine = create_engine(MIGRATION_DATABASE_URL)
    tenant_a, tenant_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    factor_a, factor_b = uuid4(), uuid4()
    activity_a, activity_b = uuid4(), uuid4()
    evidence_a, evidence_b = uuid4(), uuid4()
    snapshot_a, snapshot_b = uuid4(), uuid4()
    audit_a, audit_b = uuid4(), uuid4()
    tables = (
        "tenants",
        "memberships",
        "emission_factors",
        "activity_records",
        "evidence",
        "calculation_snapshots",
        "audit_events",
    )

    try:
        with engine.begin() as connection:
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
                "membership_a": uuid4(), "tenant_a": tenant_a, "user_a": user_a,
                "membership_b": uuid4(), "tenant_b": tenant_b, "user_b": user_b,
            })
            connection.execute(text("""
                INSERT INTO emission_factors (
                    id, tenant_id, code, name, value_kgco2e, numerator_unit,
                    denominator_unit, geography, source_name, source_url,
                    source_year, version, methodology, activity_category,
                    valid_from, approval_status
                ) VALUES
                    (:factor_a, :tenant_a, 'RLS-A', 'Tenant A factor', 1.0, 'kgCO2e',
                     'litre', 'MN', 'Source A', 'https://example.org/a', 2026, 'v1',
                     'scope1_activity_factor', 'mobile_combustion', '2026-01-01', 'pending'),
                    (:factor_b, :tenant_b, 'RLS-B', 'Tenant B factor', 1.0, 'kgCO2e',
                     'litre', 'MN', 'Source B', 'https://example.org/b', 2026, 'v1',
                     'scope1_activity_factor', 'mobile_combustion', '2026-01-01', 'pending')
            """), {
                "factor_a": factor_a, "tenant_a": tenant_a,
                "factor_b": factor_b, "tenant_b": tenant_b,
            })
            connection.execute(text("""
                INSERT INTO activity_records (
                    id, tenant_id, created_by, name, scope, category, amount, unit,
                    period_start, period_end, factor_id, data_quality
                ) VALUES
                    (:activity_a, :tenant_a, :user_a, 'Activity A', 'scope_1',
                     'mobile_combustion', 10, 'litre', '2026-01-01', '2026-12-31',
                     :factor_a, 'unreviewed'),
                    (:activity_b, :tenant_b, :user_b, 'Activity B', 'scope_1',
                     'mobile_combustion', 20, 'litre', '2026-01-01', '2026-12-31',
                     :factor_b, 'unreviewed')
            """), {
                "activity_a": activity_a, "tenant_a": tenant_a, "user_a": user_a, "factor_a": factor_a,
                "activity_b": activity_b, "tenant_b": tenant_b, "user_b": user_b, "factor_b": factor_b,
            })
            connection.execute(text("""
                INSERT INTO evidence (
                    id, tenant_id, activity_id, uploaded_by, storage_key,
                    original_filename, media_type, size_bytes, sha256, scan_status
                ) VALUES
                    (:evidence_a, :tenant_a, :activity_a, :user_a, 'tenant-a/evidence-a',
                     'a.pdf', 'application/pdf', 100, repeat('a', 64), 'clean'),
                    (:evidence_b, :tenant_b, :activity_b, :user_b, 'tenant-b/evidence-b',
                     'b.pdf', 'application/pdf', 100, repeat('b', 64), 'clean')
            """), {
                "evidence_a": evidence_a, "tenant_a": tenant_a, "activity_a": activity_a, "user_a": user_a,
                "evidence_b": evidence_b, "tenant_b": tenant_b, "activity_b": activity_b, "user_b": user_b,
            })
            connection.execute(text("""
                INSERT INTO calculation_snapshots (
                    id, tenant_id, created_by, period_start, period_end,
                    methodology_version, engine_version, input_digest, result_payload
                ) VALUES
                    (:snapshot_a, :tenant_a, :user_a, '2026-01-01', '2026-12-31',
                     'test-v1', 'test-v1', repeat('a', 64), '{}'::jsonb),
                    (:snapshot_b, :tenant_b, :user_b, '2026-01-01', '2026-12-31',
                     'test-v1', 'test-v1', repeat('b', 64), '{}'::jsonb)
            """), {
                "snapshot_a": snapshot_a, "tenant_a": tenant_a, "user_a": user_a,
                "snapshot_b": snapshot_b, "tenant_b": tenant_b, "user_b": user_b,
            })
            connection.execute(text("""
                INSERT INTO audit_events (
                    id, tenant_id, actor_user_id, action, entity_type, entity_id
                ) VALUES
                    (:audit_a, :tenant_a, :user_a, 'test.created', 'test', 'a'),
                    (:audit_b, :tenant_b, :user_b, 'test.created', 'test', 'b')
            """), {
                "audit_a": audit_a, "tenant_a": tenant_a, "user_a": user_a,
                "audit_b": audit_b, "tenant_b": tenant_b, "user_b": user_b,
            })

        with engine.begin() as connection:
            role = connection.execute(text("""
                SELECT r.rolsuper, r.rolbypassrls, r.rolcanlogin,
                       c.relowner = r.oid AS owns_tenants
                FROM pg_roles r
                CROSS JOIN pg_class c
                WHERE r.rolname = 'carbon_esg_app'
                  AND c.oid = 'public.tenants'::regclass
            """)).one()
            assert role.rolsuper is False
            assert role.rolbypassrls is False
            assert role.rolcanlogin is True
            assert role.owns_tenants is False

            privileges = connection.execute(text("""
                SELECT
                  has_table_privilege('carbon_esg_app', 'public.tenants', 'INSERT') AS tenant_insert,
                  has_table_privilege('carbon_esg_app', 'public.memberships', 'INSERT') AS membership_insert,
                  has_table_privilege('carbon_esg_app', 'public.emission_factors', 'DELETE') AS factor_delete,
                  has_column_privilege('carbon_esg_app', 'public.emission_factors', 'value_kgco2e', 'UPDATE') AS factor_value_update,
                  has_column_privilege('carbon_esg_app', 'public.emission_factors', 'approval_status', 'UPDATE') AS factor_approval_update,
                  has_column_privilege('carbon_esg_app', 'public.emission_factors', 'approved_by', 'INSERT') AS factor_reviewer_insert,
                  has_column_privilege('carbon_esg_app', 'public.emission_factors', 'approval_status', 'INSERT') AS factor_status_insert,
                  has_table_privilege('carbon_esg_app', 'public.calculation_snapshots', 'UPDATE') AS snapshot_update,
                  has_table_privilege('carbon_esg_app', 'public.audit_events', 'DELETE') AS audit_delete,
                  has_table_privilege('carbon_esg_app', 'public.activity_records', 'INSERT') AS activity_insert,
                  has_table_privilege('carbon_esg_app', 'public.audit_events', 'INSERT') AS audit_insert
            """)).one()
            assert privileges.tenant_insert is False
            assert privileges.membership_insert is False
            assert privileges.factor_delete is False
            assert privileges.factor_value_update is False
            assert privileges.factor_approval_update is True
            assert privileges.factor_reviewer_insert is False
            assert privileges.factor_status_insert is True
            assert privileges.snapshot_update is False
            assert privileges.audit_delete is False
            assert privileges.activity_insert is True
            assert privileges.audit_insert is True

            connection.execute(text("SET LOCAL ROLE carbon_esg_app"))
            for table in tables:
                assert connection.execute(
                    text(f"SELECT count(*) FROM {table}")
                ).scalar_one() == 0, f"{table} leaked rows without tenant context"

            for tenant_id in (tenant_a, tenant_b):
                connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )
                for table in tables:
                    tenant_column = "id" if table == "tenants" else "tenant_id"
                    visible = connection.execute(
                        text(f"SELECT count(*) FROM {table} WHERE {tenant_column} = :tenant"),
                        {"tenant": tenant_id},
                    ).scalar_one()
                    total_visible = connection.execute(
                        text(f"SELECT count(*) FROM {table}")
                    ).scalar_one()
                    assert visible == 1, f"{table} did not expose exactly one tenant row"
                    assert total_visible == 1, f"{table} exposed another tenant's rows"
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
            assert revision == "20261104_0009"
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
                      AND (tgtype & 4) = 4
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
            assert {"approved_at", "approval_note", "activity_category"}.issubset(columns)
            activity_columns = {
                row.column_name
                for row in connection.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'activity_records'
                """))
            }
            assert "scope_2_basis" in activity_columns
    finally:
        engine.dispose()
