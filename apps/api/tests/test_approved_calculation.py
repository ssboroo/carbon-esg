"""Integration tests for approved registry-backed inventory calculations."""
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.approved_calculation import calculate_and_persist_approved
from app.models import ActivityRecord, AuditEvent, CalculationSnapshot, EmissionFactor, Tenant, User
from app.schemas import ApprovedInventoryCalculationRequest

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="PostgreSQL integration DB is not configured"
)


def _payload(factor_id, basis="location_based"):
    return ApprovedInventoryCalculationRequest.model_validate({
        "reporting_period_start": "2026-01-01",
        "reporting_period_end": "2026-12-31",
        "records": [{
            "name": "Purchased electricity",
            "scope": "scope_2",
            "category": "purchased_electricity",
            "activity_amount": "1000",
            "activity_unit": "kWh",
            "factor_id": str(factor_id),
            "scope_2_basis": basis,
        }],
    })


def test_calculation_uses_only_approved_tenant_factor_and_persists_provenance():
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id, approved_id, pending_id = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        with Session(engine) as db:
            with db.begin():
                db.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )
                db.add(Tenant(
                    id=tenant_id,
                    legal_name="Approved Factor Calculation Test",
                    country_code="MN",
                ))
                db.add(User(
                    id=user_id,
                    email=f"{user_id}@approved-factor.invalid",
                    display_name="Approved Factor Test User",
                    is_active=True,
                ))
                db.flush()
                db.add_all([
                    EmissionFactor(
                        id=approved_id,
                        tenant_id=tenant_id,
                        code="MN-POWER-LOC-2026",
                        name="Purchased electricity: official location-based factor",
                        value_kgco2e=Decimal("0.500000000000"),
                        numerator_unit="kgCO2e",
                        denominator_unit="kWh",
                        geography="MN",
                        source_name="Official electricity source",
                        source_url="https://example.org/mn-electricity",
                        source_year=2026,
                        version="2026-v1",
                        methodology="location-based",
                        activity_category="purchased_electricity",
                        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        approval_status="approved",
                        approved_by=user_id,
                        approved_at=datetime.now(timezone.utc),
                        approval_note="Verified source, geography, period and unit.",
                    ),
                    EmissionFactor(
                        id=pending_id,
                        tenant_id=tenant_id,
                        code="MN-POWER-PENDING-2026",
                        name="Purchased electricity pending factor",
                        value_kgco2e=Decimal("0.700000000000"),
                        numerator_unit="kgCO2e",
                        denominator_unit="kWh",
                        geography="MN",
                        source_name="Unreviewed source",
                        source_url="https://example.org/pending-electricity",
                        source_year=2026,
                        version="2026-v1",
                        methodology="location-based",
                        activity_category="purchased_electricity",
                        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        approval_status="pending",
                    ),
                ])

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            with pytest.raises(HTTPException) as pending:
                calculate_and_persist_approved(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    payload=_payload(pending_id),
                )
            assert pending.value.status_code == 409
            db.rollback()

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            with pytest.raises(HTTPException) as wrong_basis:
                calculate_and_persist_approved(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    payload=_payload(approved_id, "market_based"),
                )
            assert wrong_basis.value.status_code == 422
            db.rollback()

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            result = calculate_and_persist_approved(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                payload=_payload(approved_id),
                request_id="approved-factor-calc-1",
            )
            assert result.factor_status == "approved"
            assert result.review_status == "pending_review"
            assert result.total_tco2e == Decimal("0.500000")

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            activities = db.scalars(select(ActivityRecord).where(
                ActivityRecord.tenant_id == tenant_id
            )).all()
            snapshots = db.scalars(select(CalculationSnapshot).where(
                CalculationSnapshot.tenant_id == tenant_id
            )).all()
            events = db.scalars(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id
            )).all()
            assert len(activities) == 1
            assert activities[0].factor_id == approved_id
            assert activities[0].scope_2_basis == "location_based"
            assert len(snapshots) == 1
            assert snapshots[0].result_payload["factor_status"] == "approved"
            assert snapshots[0].result_payload["review_status"] == "pending_review"
            assert snapshots[0].result_payload["scope_2_location_based_tco2e"] == "0.500000"
            assert len(snapshots[0].input_digest) == 64
            assert any(event.action == "calculation_snapshot.created_from_approved_factors" for event in events)
            assert any(event.action == "activity_record.created_from_approved_factor" for event in events)
    finally:
        engine.dispose()
