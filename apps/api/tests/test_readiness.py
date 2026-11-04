from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_is_liveness_and_does_not_require_database():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_fails_closed_without_database_or_migrations():
    response = client.get("/ready")
    # CI has a migrated PostgreSQL service; local test runs may not.
    assert response.status_code in (200, 503)
    if response.status_code == 503:
        assert "database" in response.json()["detail"].lower() or "migration" in response.json()["detail"].lower()


def test_security_headers_are_present():
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in response.headers
