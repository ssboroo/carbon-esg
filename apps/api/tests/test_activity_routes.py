"""PostgreSQL integration tests for tenant-scoped activity history."""
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.activity_routes import list_activity_records
from app.auth import TenantContext
from app.models import ActivityRecord, EmissionFactor, Tenant, User

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="PostgreSQL integration DB is not configured"
)


def test_activity_history_returns_persisted_factor_provenance_for_current_tenant():
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id, factor_id, activity_id = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        with Session(engine) as db:
            with db.begin():
                db.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )
                db.add(Tenant(
                    id=tenant_id,
                    legal_name="Activity API Tenant",
                    country_code="MN",
                ))
                db.add(User(
                    id=user_id,
                    email=f"{user_id}@activity-api.invalid",
                    display_name="Activity API User",
                    is_active=True,
                ))
                db.flush()
                db.add(EmissionFactor(
                    id=factor_id,
                    tenant_id=tenant_id,
                    code="MN-DIESEL-2026",
                    name="Mobile combustion: diesel",
                    value_kgco2e=Decimal("2.680000000000"),
                    numerator_unit="kgCO2e",
                    denominator_unit="litre",
                    geography="MN",
                    source_name="Official diesel factor",
                    source_url="https://example.org/diesel",
                    source_year=2026,
                    version="2026-v1",
                    methodology="scope1_activity_factor",
                    activity_category="mobile_combustion",
                    valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    approval_status="pending",
                ))
                db.flush()
                db.add(ActivityRecord(
                    id=activity_id,
                    tenant_id=tenant_id,
                    created_by=user_id,
                    name="Fleet diesel",
                    scope="scope_1",
                    category="mobile_combustion",
                    amount=Decimal("100.00000000"),
                    unit="litre",
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                    factor_id=factor_id,
                    data_quality="unreviewed",
                ))

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            rows = list_activity_records(
                period_start=None,
                period_end=None,
                limit=100,
                offset=0,
                tenant=TenantContext(tenant_id=tenant_id, user_id=user_id, role="viewer"),
                db=db,
            )
            assert len(rows) == 1
            assert rows[0]["id"] == activity_id
            assert rows[0]["factor_approval_status"] == "pending"
            assert rows[0]["factor_source_name"] == "Official diesel factor"
            assert rows[0]["emissions_tco2e"] == Decimal("0.268000")
    finally:
        engine.dispose()
