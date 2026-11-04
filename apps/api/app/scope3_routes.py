"""Scope 3 category applicability and materiality assessment API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import TenantContext, require_roles
from .database import get_db
from .models import AuditEvent, Scope3CategoryAssessment
from .schemas import SCOPE_3_CATEGORIES

router = APIRouter(prefix="/v1/scope3", tags=["scope-3"])

CATEGORY_LABELS = {
    "purchased_goods_and_services": "1. Purchased goods and services",
    "capital_goods": "2. Capital goods",
    "fuel_and_energy_related_activities": "3. Fuel- and energy-related activities",
    "upstream_transportation_and_distribution": "4. Upstream transportation and distribution",
    "waste_generated_in_operations": "5. Waste generated in operations",
    "business_travel": "6. Business travel",
    "employee_commuting": "7. Employee commuting",
    "upstream_leased_assets": "8. Upstream leased assets",
    "downstream_transportation_and_distribution": "9. Downstream transportation and distribution",
    "processing_of_sold_products": "10. Processing of sold products",
    "use_of_sold_products": "11. Use of sold products",
    "end_of_life_treatment_of_sold_products": "12. End-of-life treatment of sold products",
    "downstream_leased_assets": "13. Downstream leased assets",
    "franchises": "14. Franchises",
    "investments": "15. Investments",
}


class Scope3AssessmentRequest(BaseModel):
    applicability: Literal["relevant", "not_relevant", "not_assessed"]
    rationale: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_exclusion_rationale(self):
        if self.applicability == "not_relevant" and len((self.rationale or "").strip()) < 20:
            raise ValueError("A not-relevant Scope 3 category requires a rationale of at least 20 characters")
        return self


class Scope3CategoryResponse(BaseModel):
    category: str
    label: str
    reporting_year: int
    applicability: str
    rationale: str | None
    reviewed_by: UUID | None
    reviewed_at: str | None


@router.get("/categories", response_model=list[Scope3CategoryResponse])
def list_scope3_categories(
    reporting_year: int = Query(default=2026, ge=1900, le=2200),
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager", "reviewer", "viewer")),
    db: Session = Depends(get_db),
):
    records = db.scalars(select(Scope3CategoryAssessment).where(
        Scope3CategoryAssessment.tenant_id == tenant.tenant_id,
        Scope3CategoryAssessment.reporting_year == reporting_year,
    )).all()
    by_category = {record.category: record for record in records}
    return [
        {
            "category": category,
            "label": label,
            "reporting_year": reporting_year,
            "applicability": by_category[category].applicability if category in by_category else "not_assessed",
            "rationale": by_category[category].rationale if category in by_category else None,
            "reviewed_by": by_category[category].reviewed_by if category in by_category else None,
            "reviewed_at": by_category[category].reviewed_at.isoformat() if category in by_category and by_category[category].reviewed_at else None,
        }
        for category, label in CATEGORY_LABELS.items()
        if category in SCOPE_3_CATEGORIES
    ]


@router.put("/categories/{category}", response_model=Scope3CategoryResponse)
def update_scope3_category_assessment(
    category: str,
    payload: Scope3AssessmentRequest,
    request: Request,
    reporting_year: int = Query(default=2026, ge=1900, le=2200),
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    if category not in SCOPE_3_CATEGORIES:
        raise HTTPException(status_code=404, detail="Unknown Scope 3 category")

    record = db.scalar(
        select(Scope3CategoryAssessment)
        .where(
            Scope3CategoryAssessment.tenant_id == tenant.tenant_id,
            Scope3CategoryAssessment.reporting_year == reporting_year,
            Scope3CategoryAssessment.category == category,
        )
        .with_for_update()
    )
    before = None if record is None else {
        "applicability": record.applicability,
        "rationale": record.rationale,
        "reviewed_by": str(record.reviewed_by) if record.reviewed_by else None,
    }
    now = datetime.now(timezone.utc)
    if record is None:
        record = Scope3CategoryAssessment(
            id=uuid4(),
            tenant_id=tenant.tenant_id,
            reporting_year=reporting_year,
            category=category,
        )
        db.add(record)

    record.applicability = payload.applicability
    record.rationale = payload.rationale.strip() if payload.rationale else None
    record.reviewed_by = tenant.user_id if payload.applicability != "not_assessed" else None
    record.reviewed_at = now if payload.applicability != "not_assessed" else None

    request_id = request.headers.get("X-Request-ID")
    if request_id and len(request_id) > 80:
        request_id = None
    db.add(AuditEvent(
        tenant_id=tenant.tenant_id,
        actor_user_id=tenant.user_id,
        action="scope3.category_assessment.updated",
        entity_type="scope3_category_assessment",
        entity_id=str(record.id),
        before_state=before,
        after_state={
            "category": category,
            "reporting_year": reporting_year,
            "applicability": record.applicability,
            "rationale": record.rationale,
            "reviewed_by": str(record.reviewed_by) if record.reviewed_by else None,
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        },
        request_id=request_id,
    ))
    response_data = {
        "category": category,
        "label": CATEGORY_LABELS[category],
        "reporting_year": reporting_year,
        "applicability": record.applicability,
        "rationale": record.rationale,
        "reviewed_by": record.reviewed_by,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
    }
    db.commit()
    return response_data
