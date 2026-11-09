from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.inventories import (
    activity_snapshot_is_valid,
    calculate_activity_emissions,
    calculate_scope2_method_totals,
)
from app.inventory_schemas import ActivityRecordCreate, InventoryCreate
from app.main import app


def test_inventory_period_must_be_ordered():
    with pytest.raises(ValidationError):
        InventoryCreate(
            name="2026 тайлан",
            reporting_period_start=date(2026, 12, 31),
            reporting_period_end=date(2026, 1, 1),
        )


def test_inventory_name_is_trimmed():
    inventory = InventoryCreate(
        name="  2026 тайлан  ",
        reporting_period_start=date(2026, 1, 1),
        reporting_period_end=date(2026, 12, 31),
    )
    assert inventory.name == "2026 тайлан"


def test_activity_amount_must_be_positive_and_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        ActivityRecordCreate(
            name="Цахилгаан",
            scope="scope_2",
            category="purchased_electricity",
            activity_amount=Decimal("0"),
            activity_unit="kWh",
            emission_factor_id="00000000-0000-0000-0000-000000000001",
            geography_code="MNG-GRID-01",
            geography_name="Монголын төвийн эрчим хүчний систем",
        )

    with pytest.raises(ValidationError):
        ActivityRecordCreate(
            name="Цахилгаан",
            scope="scope_2",
            category="purchased_electricity",
            activity_amount=Decimal("100"),
            activity_unit="kWh",
            emission_factor_id="00000000-0000-0000-0000-000000000001",
            geography_code="MNG-GRID-01",
            geography_name="Монголын төвийн эрчим хүчний систем",
            emission_factor_kgco2e_per_unit=Decimal("999"),
        )


def test_activity_emissions_use_decimal_and_eight_place_rounding():
    assert calculate_activity_emissions(
        Decimal("12.5"),
        Decimal("0.08"),
    ) == Decimal("1.00000000")

    assert calculate_activity_emissions(
        Decimal("1"),
        Decimal("1.234567895"),
    ) == Decimal("1.23456790")


def test_factor_geography_and_validity_must_cover_the_reporting_period():
    from app.inventories import factor_applies_to_activity

    factor = SimpleNamespace(
        geography_code="MNG-GRID-01",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    inventory = SimpleNamespace(
        reporting_period_start=date(2026, 1, 1),
        reporting_period_end=date(2026, 12, 31),
    )
    assert factor_applies_to_activity(factor, inventory, "MNG-GRID-01")
    assert not factor_applies_to_activity(factor, inventory, "MNG-GRID-02")
    partial_inventory = SimpleNamespace(
        reporting_period_start=date(2025, 12, 1),
        reporting_period_end=date(2026, 12, 31),
    )
    assert not factor_applies_to_activity(factor, partial_inventory, "MNG-GRID-01")
    factor.valid_from = None
    factor.valid_to = None
    assert not factor_applies_to_activity(factor, inventory, "MNG-GRID-01")


def test_calculation_rejects_tampered_or_unverified_activity_snapshots():
    record = SimpleNamespace(
        activity_geography_code="MNG-GRID-01",
        activity_geography_name="Монголын төвийн эрчим хүчний систем",
        scope="scope_2",
        scope_2_method="location_based",
        category="purchased_electricity",
        activity_amount=Decimal("2"),
        activity_unit="kWh",
        factor_value_snapshot=Decimal("0.5"),
        factor_unit_snapshot="kWh",
        emissions_kgco2e=Decimal("1.00000000"),
    )
    factor = SimpleNamespace(
        verified=True,
        scope="scope_2",
        scope_2_method="location_based",
        category="purchased_electricity",
        gas_basis="CO2e",
        factor_unit="kWh",
        factor_value=Decimal("0.5"),
        geography_code="MNG-GRID-01",
        geography_name="Монголын төвийн эрчим хүчний систем",
        geography_boundary="grid",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    assert activity_snapshot_is_valid(record, factor)

    record.emissions_kgco2e = Decimal("1.10000000")
    assert not activity_snapshot_is_valid(record, factor)

    record.emissions_kgco2e = Decimal("1.00000000")
    factor.verified = False
    assert not activity_snapshot_is_valid(record, factor)

    factor.verified = True
    factor.valid_from = None
    assert not activity_snapshot_is_valid(record, factor)


def test_tenant_routes_require_authenticated_membership():
    client = TestClient(app)
    organization_id = "00000000-0000-0000-0000-000000000001"
    inventory_id = "00000000-0000-0000-0000-000000000002"

    assert client.get(
        f"/v1/organizations/{organization_id}/emission-factors"
    ).status_code == 401
    assert client.get(
        f"/v1/organizations/{organization_id}/inventories"
    ).status_code == 401
    assert client.post(
        f"/v1/organizations/{organization_id}/inventories",
        json={
            "name": "2026 тайлан",
            "reporting_period_start": "2026-01-01",
            "reporting_period_end": "2026-12-31",
        },
    ).status_code == 401
    assert client.post(
        f"/v1/organizations/{organization_id}/inventories/{inventory_id}/calculate"
    ).status_code == 401

def test_scope2_methods_are_calculated_and_reported_separately():
    records = [
        SimpleNamespace(scope_2_method="location_based", emissions_kgco2e=Decimal("1.25000000")),
        SimpleNamespace(scope_2_method="market_based", emissions_kgco2e=Decimal("0.90000000")),
    ]
    primary, location, market, total_location, total_market = calculate_scope2_method_totals(
        Decimal("10.00000000"),
        records,
        "location_based",
    )
    assert primary == Decimal("1.25000000")
    assert location == Decimal("1.25000000")
    assert market == Decimal("0.90000000")
    assert total_location == Decimal("11.25000000")
    assert total_market == Decimal("10.90000000")


def test_scope2_methods_are_never_added_together_and_primary_method_is_required():
    records = [
        SimpleNamespace(scope_2_method="location_based", emissions_kgco2e=Decimal("1.0")),
        SimpleNamespace(scope_2_method="market_based", emissions_kgco2e=Decimal("0.5")),
    ]
    with pytest.raises(ValueError):
        calculate_scope2_method_totals(Decimal("2"), records, "invalid")
    with pytest.raises(ValueError):
        calculate_scope2_method_totals(Decimal("2"), [records[0]], "market_based")
