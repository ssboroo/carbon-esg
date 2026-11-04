from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_calculation_endpoint_requires_bearer_token():
    response = client.post(
        "/v1/calculations",
        json={
            "reporting_period_start": "2026-01-01",
            "reporting_period_end": "2026-12-31",
            "records": [{
                "name": "Electricity",
                "scope": "scope_2",
                "category": "purchased_electricity",
                "activity_amount": "1",
                "activity_unit": "kWh",
                "emission_factor_kgco2e_per_unit": "0.5",
                "factor_unit": "kWh",
                "factor_source_name": "Test source",
                "factor_source_url": "https://example.org/factor",
                "factor_year": 2026,
                "factor_version": "test",
            }],
        },
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_identity_endpoint_requires_bearer_token():
    response = client.get(
        "/v1/me",
        headers={"X-Tenant-ID": "00000000-0000-0000-0000-000000000001"},
    )
    assert response.status_code == 401


def test_tenant_selector_is_not_an_authorization_credential():
    # Even with a tenant selector, a caller without an access token is denied.
    response = client.get(
        "/v1/me",
        headers={
            "X-Tenant-ID": "00000000-0000-0000-0000-000000000001",
            "X-User-ID": "00000000-0000-0000-0000-000000000002",
            "X-Role": "admin",
        },
    )
    assert response.status_code == 401
