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
