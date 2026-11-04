"""Real PostgreSQL tests for transactional calculation persistence."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import (
    ActivityRecord,
    AuditEvent,
    CalculationSnapshot,
    EmissionFactor,
    Tenant,
    User,
)
from app.persistence import persist_inventory_calculation
from app.schemas import InventoryCalculationRequest
from app.calculator import calculate_inventory

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not MIGRATION_DATABASE_URL,
    reason="Runtime and migration PostgreSQL URLs are required",
)


def make_request():
    return InventoryCalculationRequest.model_validate({
        "reporting_period_start": "2026-01-01",
        "reporting_period_end": "2026-12-31",
        "records": [
            {
                "name": "Diesel fleet",
                "scope": "scope_1",
                "category": "mobile_combustion",
                "activity_amount": "100",
                "activity_unit": "litre",
                "emission_factor_kgco2e_per_unit": "2.68",
                "factor_unit": "litre",
                "factor_source_name": "Test source diesel",
                "factor_source_url": "https://example.org/diesel",
                "factor_year": 2026,
                "factor_version": "test-2026-v1",
            },
            {
                "name": "Purchased electricity",
                "scope": "scope_2",
                "category": "purchased_electricity",
                "activity_amount": "1000",
                "activity_unit": "kWh",
                "emission_factor_kgco2e_per_unit": "0.5",
                "factor_unit": "kWh",
                "factor_source_name": "Test source grid",
                "factor_source_url": "https://example.org/grid",
                "factor_year": 2026,
                "factor_version": "test-2026-v1",
                "scope_2_basis": "location_based",
            },
        ],
    })


def test_persist_calculation_records_provenance_snapshot_and_audit_atomically():
    seed_engine = create_engine(MIGRATION_DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id = uuid4(), uuid4()
    try:
        with Session(seed_engine) as seed:
            with seed.begin():
                seed.add(Tenant(
                    id=tenant_id,
                    legal_name="Persistence Integration Test",
                    country_code="MN",
                ))
                seed.add(User(
                    id=user_id,
                    email=f"{user_id}@persistence-test.invalid",
                    display_name="Persistence Test User",
                    is_active=True,
                ))

        with Session(engine) as db:
            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            request = make_request()
            result = calculate_inventory(request)
            snapshot_id = persist_inventory_calculation(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                request=request,
                result=result,
                request_id="integration-persist-1",
            )
            assert snapshot_id is not None

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            factors = db.scalars(
                select(EmissionFactor).where(EmissionFactor.tenant_id == tenant_id)
            ).all()
            activities = db.scalars(
                select(ActivityRecord).where(ActivityRecord.tenant_id == tenant_id)
            ).all()
            snapshot = db.scalar(
                select(CalculationSnapshot).where(CalculationSnapshot.id == snapshot_id)
            )
            audit_events = db.scalars(
                select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
            ).all()

            assert len(factors) == 2
            assert all(factor.approval_status == "pending" for factor in factors)
            assert len(activities) == 2
            assert all(activity.data_quality == "unreviewed" for activity in activities)
            assert snapshot is not None
            assert len(snapshot.input_digest) == 64
            assert snapshot.result_payload["review_status"] == "pending_review"
            assert len(audit_events) == 5
            assert {event.action for event in audit_events} == {
                "emission_factor.submitted",
                "activity_record.created",
                "calculation_snapshot.created",
            }

            # Snapshots are append-only at the database layer, not merely by convention.
            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.execute(
                        text("UPDATE calculation_snapshots SET engine_version = 'tampered' WHERE id = :id"),
                        {"id": snapshot_id},
                    )
            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.execute(
                        text("DELETE FROM calculation_snapshots WHERE id = :id"),
                        {"id": snapshot_id},
                    )

            # Reusing the same factor provenance key with a changed numeric value
            # must not silently overwrite the original factor.
            changed_payload = request.model_dump(mode="json")
            changed_payload["records"][0]["emission_factor_kgco2e_per_unit"] = "9.99"
            changed_request = InventoryCalculationRequest.model_validate(changed_payload)
            with pytest.raises(ValueError, match="different contents"):
                persist_inventory_calculation(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    request=changed_request,
                    result=calculate_inventory(changed_request),
                    request_id="integration-persist-conflict",
                )
            db.rollback()
    finally:
        engine.dispose()
        seed_engine.dispose()
