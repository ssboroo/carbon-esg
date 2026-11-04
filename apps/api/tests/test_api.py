from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def valid_payload() -> dict:
    return {
        "reporting_period_start": "2026-01-01",
        "reporting_period_end": "2026-12-31",
        "records": [
            {
                "name": "Тээврийн хэрэгслийн дизель түлш",
                "scope": "scope_1",
                "category": "mobile_combustion",
                "activity_amount": "100",
                "activity_unit": "litre",
                "emission_factor_kgco2e_per_unit": "2.68",
                "factor_unit": "litre",
                "factor_source_name": "Туршилтын эх сурвалж",
                "factor_source_url": "https://example.org/factors/diesel",
                "factor_year": 2026,
                "factor_version": "test-2026-v1",
            },
            {
                "name": "Худалдан авсан цахилгаан",
                "scope": "scope_2",
                "category": "purchased_electricity",
                "activity_amount": "1000",
                "activity_unit": "kWh",
                "emission_factor_kgco2e_per_unit": "0.5",
                "factor_unit": "kWh",
                "factor_source_name": "Туршилтын цахилгаан эх сурвалж",
                "factor_source_url": "https://example.org/factors/grid",
                "factor_year": 2026,
                "factor_version": "test-2026-v1",
            },
        ],
    }


def test_health_endpoint_returns_service_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "carbon-esg-api"}


def test_root_endpoint_exposes_api_metadata():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Carbon ESG API",
        "version": "0.2.0",
        "docs": "/docs",
    }


def test_calculation_endpoint_returns_deterministic_totals_and_factor_provenance():
    response = client.post("/v1/calculations", json=valid_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["scope_1_tco2e"] == "0.268000"
    assert body["scope_2_tco2e"] == "0.500000"
    assert body["total_tco2e"] == "0.768000"
    assert body["records"][0]["factor_source_name"] == "Туршилтын эх сурвалж"
    assert body["records"][1]["factor_version"] == "test-2026-v1"
    assert body["records"][1]["factor_source_url"] == "https://example.org/factors/grid"


def test_calculation_endpoint_rejects_missing_factor_instead_of_guessing():
    payload = valid_payload()
    del payload["records"][0]["emission_factor_kgco2e_per_unit"]

    response = client.post("/v1/calculations", json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "emission_factor_kgco2e_per_unit"
        for error in response.json()["detail"]
    )


def test_calculation_endpoint_rejects_unit_mismatch():
    payload = valid_payload()
    payload["records"][0]["factor_unit"] = "gallon"

    response = client.post("/v1/calculations", json=payload)

    assert response.status_code == 422


def test_calculation_endpoint_rejects_untrusted_http_factor_source():
    payload = valid_payload()
    payload["records"][0]["factor_source_url"] = "http://example.org/factors/diesel"

    response = client.post("/v1/calculations", json=payload)

    assert response.status_code == 422


def test_calculation_endpoint_rejects_unknown_fields():
    payload = valid_payload()
    payload["records"][0]["ai_suggested_factor"] = "not-allowed"

    response = client.post("/v1/calculations", json=payload)

    assert response.status_code == 422


def test_cors_allows_local_web_development_origin():
    response = client.options(
        "/v1/calculations",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
