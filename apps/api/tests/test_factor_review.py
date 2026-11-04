"""PostgreSQL integration tests for human emission-factor approval."""
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.factor_review import approve_emission_factor
from app.models import AuditEvent, EmissionFactor, Tenant, User

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="PostgreSQL integration DB is not configured"
)


def test_reviewer_approval_is_audited_tenant_scoped_and_immutable():
    engine = create_engine(DATABASE_URL)
    tenant_id, other_tenant_id, reviewer_id, factor_id = (
        uuid4(), uuid4(), uuid4(), uuid4()
    )
    try:
        with Session(engine) as db:
            with db.begin():
                db.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )
                db.add_all([
                    Tenant(id=tenant_id, legal_name="Factor Review Tenant", country_code="MN"),
                    Tenant(id=other_tenant_id, legal_name="Other Tenant", country_code="MN"),
                    User(
                        id=reviewer_id,
                        email=f"{reviewer_id}@factor-review.invalid",
                        display_name="Factor Reviewer",
                        is_active=True,
                    ),
                ])
                db.flush()
                db.add(EmissionFactor(
                    id=factor_id,
                    tenant_id=tenant_id,
                    code="MN-GRID-2026",
                    name="Mongolia electricity test factor",
                    value_kgco2e=Decimal("0.500000000000"),
                    numerator_unit="kgCO2e",
                    denominator_unit="kWh",
                    geography="MN",
                    source_name="Official test source",
                    source_url="https://example.org/mn-grid",
                    source_year=2026,
                    version="2026-v1",
                    methodology="location-based",
                    valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    approval_status="pending",
                ))

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            with pytest.raises(HTTPException) as missing:
                approve_emission_factor(
                    db,
                    tenant_id=other_tenant_id,
                    reviewer_user_id=reviewer_id,
                    factor_id=factor_id,
                    note="Checked source, year, geography and unit.",
                )
            assert missing.value.status_code == 404
            db.rollback()

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            factor = approve_emission_factor(
                db,
                tenant_id=tenant_id,
                reviewer_user_id=reviewer_id,
                factor_id=factor_id,
                note="Verified source, geography, year and unit against publisher data.",
                request_id="factor-review-test-1",
            )
            assert factor.approval_status == "approved"
            assert factor.approved_by == reviewer_id
            assert factor.approved_at is not None
            assert factor.approval_note.startswith("Verified source")

            event = db.scalar(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "emission_factor.approved",
                AuditEvent.entity_id == str(factor_id),
            ))
            assert event is not None
            assert event.actor_user_id == reviewer_id
            assert event.before_state["approval_status"] == "pending"
            assert event.after_state["approval_status"] == "approved"

            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.execute(
                        text("UPDATE emission_factors SET value_kgco2e = 9.99 WHERE id = :id"),
                        {"id": factor_id},
                    )
            with pytest.raises(DBAPIError):
                with db.begin_nested():
                    db.execute(
                        text("DELETE FROM emission_factors WHERE id = :id"),
                        {"id": factor_id},
                    )
            db.rollback()
    finally:
        engine.dispose()
