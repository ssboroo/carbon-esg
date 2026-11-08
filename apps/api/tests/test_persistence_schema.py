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
    assert {"source_name", "source_url", "factor_year", "version"} <= set(table.columns.keys())


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
