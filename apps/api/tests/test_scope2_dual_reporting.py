"""Unit tests for Scope 2 dual reporting; the two methods must not be summed."""
from datetime import date
from decimal import Decimal

from app.calculator import calculate_inventory
from app.schemas import InventoryCalculationRequest


def test_scope2_location_and_market_based_results_are_reported_separately():
    request = InventoryCalculationRequest.model_validate({
        "reporting_period_start": date(2026, 1, 1),
        "reporting_period_end": date(2026, 12, 31),
        "records": [
            {
                "name": "Electricity location-based",
                "scope": "scope_2",
                "category": "purchased_electricity",
                "activity_amount": "1000",
                "activity_unit": "kWh",
                "emission_factor_kgco2e_per_unit": "0.5",
                "factor_unit": "kWh",
                "factor_source_name": "Test source location",
                "factor_source_url": "https://example.org/location",
                "factor_year": 2026,
                "factor_version": "loc-v1",
                "scope_2_basis": "location_based",
            },
            {
                "name": "Electricity market-based",
                "scope": "scope_2",
                "category": "purchased_electricity",
                "activity_amount": "1000",
                "activity_unit": "kWh",
                "emission_factor_kgco2e_per_unit": "0.2",
                "factor_unit": "kWh",
                "factor_source_name": "Test source market",
                "factor_source_url": "https://example.org/market",
                "factor_year": 2026,
                "factor_version": "market-v1",
                "scope_2_basis": "market_based",
            },
        ],
    })
    result = calculate_inventory(request)
    assert result.scope_2_location_based_tco2e == Decimal("0.500000")
    assert result.scope_2_market_based_tco2e == Decimal("0.200000")
    assert result.scope_2_tco2e == Decimal("0.500000")
    assert result.total_location_based_tco2e == Decimal("0.500000")
    assert result.total_market_based_tco2e == Decimal("0.200000")
    assert result.total_tco2e == Decimal("0.500000")
