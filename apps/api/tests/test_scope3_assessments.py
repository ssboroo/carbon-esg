"""Tenant-scoped Scope 3 applicability and materiality assessment tests."""
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth import TenantContext
from app.models import AuditEvent, Scope3CategoryAssessment, Tenant, User
from app.scope3_routes import (
    Scope3AssessmentRequest,
    list_scope3_categories,
    update_scope3_category_assessment,
)

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not MIGRATION_DATABASE_URL,
    reason="Runtime and migration PostgreSQL URLs are required",
)


def test_scope3_assessments_require_exclusion_reason_and_are_audited():
    seed_engine = create_engine(MIGRATION_DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id = uuid4(), uuid4()
    try:
        with Session(seed_engine) as seed:
            with seed.begin():
                seed.add(Tenant(
                    id=tenant_id,
                    legal_name="Scope 3 Assessment Tenant",
                    country_code="MN",
                ))
                seed.add(User(
                    id=user_id,
                    email=f"{user_id}@scope3-assessment.invalid",
                    display_name="Scope 3 Reviewer",
                    is_active=True,
                ))

        with Session(engine) as db:
            tenant = TenantContext(tenant_id=tenant_id, user_id=user_id, role="manager")
            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            categories = list_scope3_categories(
                reporting_year=2026,
                tenant=tenant,
                db=db,
            )
            assert len(categories) == 15
            assert all(item["applicability"] == "not_assessed" for item in categories)

            with pytest.raises(ValidationError):
                Scope3AssessmentRequest(
                    applicability="not_relevant",
                    rationale="Too short",
                )

            request = Request({"type": "http", "headers": []})
            response = update_scope3_category_assessment(
                category="investments",
                payload=Scope3AssessmentRequest(
                    applicability="not_relevant",
                    rationale="No investments or financing activities during this reporting year.",
                ),
                request=request,
                reporting_year=2026,
                tenant=tenant,
                db=db,
            )
            assert response["applicability"] == "not_relevant"
            assert response["reviewed_by"] == user_id

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            saved = db.scalar(select(Scope3CategoryAssessment).where(
                Scope3CategoryAssessment.tenant_id == tenant_id,
                Scope3CategoryAssessment.category == "investments",
            ))
            event = db.scalar(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "scope3.category_assessment.updated",
            ))
            assert saved is not None
            assert saved.applicability == "not_relevant"
            assert saved.reviewed_by == user_id
            assert event is not None
            assert event.after_state["reporting_year"] == 2026
            assert event.after_state["applicability"] == "not_relevant"

            updated = update_scope3_category_assessment(
                category="investments",
                payload=Scope3AssessmentRequest(
                    applicability="relevant",
                    rationale="Investment activity was identified and will be quantified.",
                ),
                request=request,
                reporting_year=2026,
                tenant=tenant,
                db=db,
            )
            assert updated["applicability"] == "relevant"
    finally:
        engine.dispose()
        seed_engine.dispose()
