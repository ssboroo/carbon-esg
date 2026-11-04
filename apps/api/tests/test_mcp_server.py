import pytest
from pydantic import ValidationError

from app.mcp_server import calculate_scope12_preview


def valid_payload():
    return {
        "reporting_period_start": "2026-01-01",
        "reporting_period_end": "2026-12-31",
        "records": [{
            "name": "Office electricity",
            "scope": "scope_2",
            "category": "purchased_electricity",
            "activity_amount": "1000",
            "activity_unit": "kWh",
            "emission_factor_kgco2e_per_unit": "0.5",
            "factor_unit": "kWh",
            "factor_source_name": "Official factor register",
            "factor_source_url": "https://example.gov.mn/factors",
            "factor_year": 2026,
            "factor_version": "2026.1",
        }],
    }


def test_calculation_preview_uses_engine_and_preserves_factor_provenance():
    result = calculate_scope12_preview(valid_payload())
    assert result["scope_2_tco2e"] == "0.500000"
    assert result["total_tco2e"] == "0.500000"
    assert result["records"][0]["factor_source_url"] == "https://example.gov.mn/factors"
    assert result["records"][0]["factor_version"] == "2026.1"


def test_rejects_non_https_factor_source():
    payload = valid_payload()
    payload["records"][0]["factor_source_url"] = "http://example.gov.mn/factor"
    with pytest.raises(ValidationError):
        calculate_scope12_preview(payload)


def test_rejects_mismatched_units():
    payload = valid_payload()
    payload["records"][0]["factor_unit"] = "MWh"
    with pytest.raises(ValidationError):
        calculate_scope12_preview(payload)


def test_rejects_scope_three_until_supported_by_calculation_schema():
    payload = valid_payload()
    payload["records"][0]["scope"] = "scope_3"
    with pytest.raises(ValidationError):
        calculate_scope12_preview(payload)
