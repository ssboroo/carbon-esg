from fastapi.testclient import TestClient

from app.db import set_identity_context, set_tenant_context
from app.main import app
from app.organization_schemas import OrganizationCreate


class FakeSession:
    def __init__(self):
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))


def test_organization_routes_require_authenticated_identity():
    client = TestClient(app)

    assert client.get("/v1/organizations").status_code == 401
    assert client.post(
        "/v1/organizations",
        json={"name": "Test organization"},
    ).status_code == 401


def test_identity_context_is_transaction_local():
    session = FakeSession()
    set_identity_context(session, "neon-user-subject")

    sql, params = session.calls[0]
    assert "app.current_user_subject" in sql
    assert "true" in sql
    assert params == {"subject": "neon-user-subject"}


def test_tenant_context_is_transaction_local():
    session = FakeSession()
    set_tenant_context(session, "00000000-0000-0000-0000-000000000001")

    sql, params = session.calls[0]
    assert "app.current_organization_id" in sql
    assert "true" in sql
    assert params == {"organization_id": "00000000-0000-0000-0000-000000000001"}


def test_organization_name_is_trimmed_and_slug_is_constrained():
    request = OrganizationCreate(name="  Монгол компани  ", slug="mongol-company")
    assert request.name == "Монгол компани"
    assert request.slug == "mongol-company"
