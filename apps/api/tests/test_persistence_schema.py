from app import models  # noqa: F401
from app.db import Base


def test_tenant_schema_contains_expected_entities():
    assert {
        "organizations",
        "organization_memberships",
        "emission_factors",
        "inventories",
        "activity_records",
        "calculation_runs",
        "audit_events",
    } <= set(Base.metadata.tables)


def test_activity_foreign_keys_include_organization_id():
    table = Base.metadata.tables["activity_records"]
    foreign_key_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.foreign_key_constraints
    }
    assert ("organization_id", "inventory_id") in foreign_key_column_sets
    assert ("organization_id", "emission_factor_id") in foreign_key_column_sets


def test_emission_factors_are_versioned_and_provenanced():
    table = Base.metadata.tables["emission_factors"]
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("organization_id", "factor_code", "version") in unique_column_sets
    assert {"source_name", "source_url", "factor_year", "version", "geography_code", "geography_name", "geography_boundary", "valid_from", "valid_to"} <= set(table.columns.keys())


def test_calculation_runs_keep_reproducible_input_snapshot():
    table = Base.metadata.tables["calculation_runs"]
    assert "input_snapshot" in table.columns
    assert "methodology_version" in table.columns

def test_organization_rls_allows_verified_members_to_discover_workspaces():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0001_tenant_esg_schema.py"
    ).read_text(encoding="utf-8")

    assert "CREATE POLICY organizations_member_select ON organizations" in migration
    assert "membership.user_subject = NULLIF(current_setting('app.current_user_subject', true), '')" in migration
    assert "CREATE POLICY organizations_create_selected ON organizations" in migration

def test_scope2_method_fields_are_persisted_separately():
    factors = Base.metadata.tables["emission_factors"]
    activities = Base.metadata.tables["activity_records"]
    inventories = Base.metadata.tables["inventories"]
    runs = Base.metadata.tables["calculation_runs"]
    assert "scope_2_method" in factors.columns
    assert "scope_2_method" in activities.columns
    assert {"activity_geography_code", "activity_geography_name"} <= set(activities.columns.keys())
    assert "scope_2_primary_method" in inventories.columns
    assert {
        "scope_2_location_based_kgco2e",
        "scope_2_market_based_kgco2e",
        "total_location_based_kgco2e",
        "total_market_based_kgco2e",
    } <= set(runs.columns.keys())

def test_membership_rls_only_exposes_the_verified_subject():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0001_tenant_esg_schema.py"
    ).read_text(encoding="utf-8")

    membership_policy = migration.split("CREATE POLICY membership_self_only", 1)[1]
    membership_policy = membership_policy.split('"""', 1)[0]
    assert "USING (" in membership_policy
    assert "user_subject = NULLIF(current_setting('app.current_user_subject', true), '')" in membership_policy
    assert "OR organization_id" not in membership_policy
    assert "AND user_subject = NULLIF(current_setting('app.current_user_subject', true), '')" in membership_policy
    organization_policy = migration.split("CREATE POLICY organizations_member_select", 1)[1].split('""")', 1)[0]
    assert "EXISTS (" in organization_policy
    assert "OR id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid" not in organization_policy

def test_alembic_revision_ids_fit_default_version_column():
    import ast
    from pathlib import Path

    migrations = Path(__file__).parents[1] / "migrations" / "versions"
    for migration_path in migrations.glob("*.py"):
        module = ast.parse(migration_path.read_text(encoding="utf-8"))
        revision = next(
            node.value.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "revision" for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        assert len(revision) <= 32, f"{migration_path.name} revision ID is too long"

def test_legacy_scope2_rows_are_marked_and_new_unclassified_rows_are_blocked():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0005_scope2_dual_method_reporting.py"
    ).read_text(encoding="utf-8")
    assert "SET scope_2_method = 'legacy_unclassified'" in migration
    assert "AS RESTRICTIVE FOR INSERT WITH CHECK" in migration
    assert "scope_2_method IN ('location_based', 'market_based')" in migration


def test_factor_geography_migration_does_not_guess_legacy_validity_dates():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0006_factor_geography_applicability.py"
    ).read_text(encoding="utf-8")
    assert "LEGACY_UNSPECIFIED" in migration
    assert "valid_from IS NULL AND valid_to IS NULL" in migration
    assert "UPDATE emission_factors" not in migration


def test_factor_validity_constraint_allows_only_both_unknown_or_ordered_dates():
    factors = Base.metadata.tables["emission_factors"]
    constraint = next(
        item for item in factors.constraints if item.name == "ck_factor_validity_period"
    )
    sql = str(constraint.sqltext)
    assert "valid_from IS NULL AND valid_to IS NULL" in sql
    assert "valid_from <= valid_to" in sql
