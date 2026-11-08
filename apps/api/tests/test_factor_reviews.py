from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.factor_schemas import EmissionFactorCreate, FactorReviewDecision
from app.factor_reviews import _require_independent_reviewer
from app.factor_status import factor_approval_status, is_factor_approved
from app.inventories import activity_snapshot_is_valid
from app.main import app


def valid_factor_payload() -> dict:
    return {
        "factor_code": "MN-GRID-2026",
        "name": "Монголын цахилгаан эрчим хүч",
        "scope": "scope_2",
        "scope_2_method": "location_based",
        "category": "purchased_electricity",
        "factor_value": "0.500000000000",
        "factor_unit": "kWh",
        "gas_basis": "CO2e",
        "source_name": "Албан ёсны эх сурвалж",
        "source_url": "https://example.org/factors/mn-grid-2026",
        "source_document": "Grid factors 2026, table 1",
        "factor_year": 2026,
        "version": "2026-v1",
    }


def test_factor_submission_requires_https_provenance_and_normalizes_text():
    payload = valid_factor_payload()
    payload["name"] = "  Монголын цахилгаан эрчим хүч  "
    payload["factor_unit"] = " kWh "
    factor = EmissionFactorCreate(**payload)

    assert factor.name == "Монголын цахилгаан эрчим хүч"
    assert factor.factor_unit == "kWh"
    assert factor.factor_value == Decimal("0.500000000000")
    assert factor.source_url.scheme == "https"


def test_factor_submission_rejects_http_url_and_unknown_fields():
    payload = valid_factor_payload()
    payload["source_url"] = "http://example.org/factors/mn-grid-2026"
    with pytest.raises(ValidationError):
        EmissionFactorCreate(**payload)

    payload = valid_factor_payload()
    payload["ai_generated_factor"] = True
    with pytest.raises(ValidationError):
        EmissionFactorCreate(**payload)


def test_factor_submission_rejects_scope_category_mismatch():
    payload = valid_factor_payload()
    payload["scope"] = "scope_1"
    with pytest.raises(ValidationError):
        EmissionFactorCreate(**payload)


def test_factor_review_decision_requires_a_substantive_note():
    with pytest.raises(ValidationError):
        FactorReviewDecision(decision="approved", note="   ")

    decision = FactorReviewDecision(
        decision="approved",
        note="  Эх сурвалж, он, газарзүй болон нэгжийг тулгаж шалгав.  ",
    )
    assert decision.note.startswith("Эх сурвалж")
    assert len(decision.note) >= 10


def test_only_approved_review_or_legacy_verified_factor_is_usable():
    factor = SimpleNamespace(verified=False)
    assert not is_factor_approved(factor, None)
    assert not is_factor_approved(factor, "rejected")
    assert is_factor_approved(factor, "approved")
    assert factor_approval_status(factor, None) == "pending"
    assert factor_approval_status(factor, "rejected") == "rejected"

    legacy_factor = SimpleNamespace(verified=True)
    assert is_factor_approved(legacy_factor, None)
    assert factor_approval_status(legacy_factor, None) == "approved"


def test_activity_snapshot_accepts_approved_review_without_mutating_factor():
    record = SimpleNamespace(
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
        verified=False,
        scope="scope_2",
        scope_2_method="location_based",
        category="purchased_electricity",
        gas_basis="CO2e",
        factor_unit="kWh",
        factor_value=Decimal("0.5"),
    )

    assert activity_snapshot_is_valid(record, factor, "approved")
    assert not activity_snapshot_is_valid(record, factor, None)
    assert not activity_snapshot_is_valid(record, factor, "rejected")


def test_factor_review_endpoints_require_authenticated_tenant_membership():
    client = TestClient(app)
    organization_id = "00000000-0000-0000-0000-000000000001"
    factor_id = "00000000-0000-0000-0000-000000000002"
    base = f"/v1/organizations/{organization_id}/emission-factors"

    assert client.get(base + "/review-queue").status_code == 401
    assert client.post(base, json=valid_factor_payload()).status_code == 401
    assert client.post(
        base + f"/{factor_id}/review",
        json={
            "decision": "approved",
            "note": "Эх сурвалж, он, газарзүй болон нэгжийг шалгав.",
        },
    ).status_code == 401


def test_factor_submitter_cannot_review_own_submission():
    with pytest.raises(HTTPException) as error:
        _require_independent_reviewer("user-submitter", "user-submitter")
    assert error.value.status_code == 403


def test_factor_review_requires_known_submitter_identity():
    with pytest.raises(HTTPException) as error:
        _require_independent_reviewer(None, "user-reviewer")
    assert error.value.status_code == 409


def test_independent_factor_reviewer_is_allowed():
    _require_independent_reviewer("user-submitter", "user-reviewer")

def test_scope2_factor_requires_an_explicit_method():
    payload = valid_factor_payload()
    payload.pop("scope_2_method")
    with pytest.raises(ValidationError):
        EmissionFactorCreate(**payload)

    payload = valid_factor_payload()
    payload["scope"] = "scope_1"
    payload["category"] = "stationary_combustion"
    payload["scope_2_method"] = None
    EmissionFactorCreate(**payload)
