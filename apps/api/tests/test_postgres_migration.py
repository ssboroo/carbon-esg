"""PostgreSQL migration smoke tests. CI runs these against a real PostgreSQL service."""
import os

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


def test_alembic_revision_is_applied():
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert revision == "20261104_0002"
    finally:
        engine.dispose()
