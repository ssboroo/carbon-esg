"""Scope 3 category calculations and Scope 2 dual-method totals."""
from datetime import date
from decimal import Decimal

from app.calculator import calculate_inventory
from app.schemas import InventoryCalculationRequest, SCOPE_3_CATEGORIES


def _record(name, scope, category, amount, factor, basis=None):
    return {
        "name": name,
        "scope": scope,
        "category": category,
        "activity_amount": str(amount),
        "activity_unit": "kg",
        "emission_factor_kgco2e_per_unit": str(factor),
        "factor_unit": "kg",
        "factor_source_name": "Test source",
        "factor_source_url": "https://example.org/factor",
        "factor_year": 2026,
        "factor_version": "v1",
        **({"scope_2_basis": basis} if basis else {}),
    }


def test_all_fifteen_scope3_categories_are_available():
    assert len(SCOPE_3_CATEGORIES) == 15


def test_scope3_categories_are_aggregated_and_added_to_both_scope2_totals():
    request = InventoryCalculationRequest.model_validate({
        "reporting_period_start": date(2026, 1, 1),
        "reporting_period_end": date(2026, 12, 31),
        "records": [
            _record("Scope 1 fuel", "scope_1", "mobile_combustion", 1000, "0.5"),
            _record("Scope 2 location", "scope_2", "purchased_electricity", 1000, "0.4", "location_based"),
            _record("Scope 2 market", "scope_2", "purchased_electricity", 1000, "0.2", "market_based"),
            _record("Purchased goods", "scope_3", "purchased_goods_and_services", 1000, "0.3"),
            _record("Business travel", "scope_3", "business_travel", 2000, "0.1"),
        ],
    })
    result = calculate_inventory(request)
    assert result.scope_1_tco2e == Decimal("0.500000")
    assert result.scope_2_location_based_tco2e == Decimal("0.400000")
    assert result.scope_2_market_based_tco2e == Decimal("0.200000")
    assert result.scope_3_tco2e == Decimal("0.500000")
    assert result.scope_3_category_totals["purchased_goods_and_services"] == Decimal("0.300000")
    assert result.scope_3_category_totals["business_travel"] == Decimal("0.200000")
    assert result.total_location_based_tco2e == Decimal("1.400000")
    assert result.total_market_based_tco2e == Decimal("1.200000")
    assert result.total_tco2e == Decimal("1.400000")
