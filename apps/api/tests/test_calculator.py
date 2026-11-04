from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.calculator import calculate_inventory
from app.main import app
from app.schemas import InventoryCalculationRequest
from app.auth import TenantContext, get_current_membership
from app.database import get_db

client = TestClient(app)


def make_request():
    return InventoryCalculationRequest.model_validate(
        {
            "reporting_period_start": "2026-01-01",
            "reporting_period_end": "2026-12-31",
            "records": [
                {
                    "name": "Company vehicle diesel",
                    "scope": "scope_1",
                    "category": "mobile_combustion",
                    "activity_amount": "100",
                    "activity_unit": "litre",
                    "emission_factor_kgco2e_per_unit": "2.68",
                    "factor_unit": "litre",
                    "factor_source_name": "Test factor source",
                    "factor_source_url": "https://example.org/factors/diesel",
                    "factor_year": 2026,
                    "factor_version": "test-1",
                },
                {
                    "name": "Purchased electricity",
                    "scope": "scope_2",
                    "category": "purchased_electricity",
                    "activity_amount": "1000",
                    "activity_unit": "kWh",
                    "emission_factor_kgco2e_per_unit": "0.5",
                    "factor_unit": "kWh",
                    "factor_source_name": "Test grid factor source",
                    "factor_source_url": "https://example.org/factors/grid",
                    "factor_year": 2026,
                    "factor_version": "test-1",
                },
            ],
        }
    )


def test_calculates_scope_totals_and_preserves_factor_provenance():
    result = calculate_inventory(make_request())

    assert result.scope_1_tco2e == Decimal("0.268000")
    assert result.scope_2_tco2e == Decimal("0.500000")
    assert result.total_tco2e == Decimal("0.768000")
    assert result.records[0].factor_source_name == "Test factor source"
    assert result.records[1].factor_version == "test-1"
    assert result.review_status == "preview"
    assert result.snapshot_id is None


def test_rejects_mismatched_activity_and_factor_units():
    payload = make_request().model_dump(mode="json")
    payload["records"][0]["factor_unit"] = "gallon"

    with pytest.raises(ValidationError):
        InventoryCalculationRequest.model_validate(payload)


def test_rejects_scope_category_mismatch():
    payload = make_request().model_dump(mode="json")
    payload["records"][0]["category"] = "purchased_electricity"

    with pytest.raises(ValidationError):
        InventoryCalculationRequest.model_validate(payload)


def test_rejects_http_factor_source():
    payload = make_request().model_dump(mode="json")
    payload["records"][0]["factor_source_url"] = "http://example.org/factor"

    with pytest.raises(ValidationError):
        InventoryCalculationRequest.model_validate(payload)


def test_rejects_reversed_reporting_period():
    payload = make_request().model_dump(mode="json")
    payload["reporting_period_start"] = "2026-12-31"
    payload["reporting_period_end"] = "2026-01-01"

    with pytest.raises(ValidationError):
        InventoryCalculationRequest.model_validate(payload)


def test_health_endpoint_is_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_calculation_endpoint_persists_and_marks_result_pending_review(monkeypatch):
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    user_id = UUID("00000000-0000-0000-0000-000000000002")
    snapshot_id = UUID("00000000-0000-0000-0000-000000000003")
    app.dependency_overrides[get_current_membership] = lambda: TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role="manager",
    )
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(
        "app.main.persist_inventory_calculation",
        lambda *args, **kwargs: snapshot_id,
    )
    try:
        response = client.post(
            "/v1/calculations",
            headers={"X-Request-ID": "calc-test-1"},
            json=make_request().model_dump(mode="json"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_tco2e"] == "0.768000"
    assert payload["records"][0]["factor_source_name"] == "Test factor source"
    assert payload["snapshot_id"] == str(snapshot_id)
    assert payload["review_status"] == "pending_review"


def test_current_user_endpoint_rejects_anonymous_requests():
    response = client.get("/v1/me", headers={"X-Tenant-ID": "00000000-0000-0000-0000-000000000001"})
    assert response.status_code == 401
