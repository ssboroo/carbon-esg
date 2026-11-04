"""Tenant-scoped emission-factor review endpoints."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import TenantContext, require_roles
from .database import get_db
from .models import EmissionFactor
from .factor_review import approve_emission_factor

router = APIRouter(prefix="/v1/emission-factors", tags=["emission-factors"])


class FactorApprovalRequest(BaseModel):
    note: str = Field(min_length=10, max_length=2000)


class FactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    value_kgco2e: str
    numerator_unit: str
    denominator_unit: str
    activity_category: str
    methodology: str
    geography: str
    source_name: str
    source_url: str
    source_year: int
    version: str
    approval_status: str
    approved_by: UUID | None
    approved_at: str | None
    approval_note: str | None


@router.get("", response_model=list[FactorResponse])
def list_emission_factors(
    approval_status: Literal["pending", "approved"] | None = None,
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager", "reviewer", "viewer")),
    db: Session = Depends(get_db),
):
    query = select(EmissionFactor).where(EmissionFactor.tenant_id == tenant.tenant_id)
    if approval_status:
        query = query.where(EmissionFactor.approval_status == approval_status)
    factors = db.scalars(query.order_by(EmissionFactor.created_at.desc()).limit(500)).all()
    return [
        {
            "id": factor.id,
            "code": factor.code,
            "name": factor.name,
            "value_kgco2e": str(factor.value_kgco2e),
            "numerator_unit": factor.numerator_unit,
            "denominator_unit": factor.denominator_unit,
            "activity_category": factor.activity_category,
            "methodology": factor.methodology,
            "geography": factor.geography,
            "source_name": factor.source_name,
            "source_url": factor.source_url,
            "source_year": factor.source_year,
            "version": factor.version,
            "approval_status": factor.approval_status,
            "approved_by": factor.approved_by,
            "approved_at": factor.approved_at.isoformat() if factor.approved_at else None,
            "approval_note": factor.approval_note,
        }
        for factor in factors
    ]


@router.post("/{factor_id}/approve", response_model=FactorResponse)
def approve_factor(
    factor_id: UUID,
    payload: FactorApprovalRequest,
    request: Request,
    tenant: TenantContext = Depends(require_roles("owner", "admin", "reviewer")),
    db: Session = Depends(get_db),
):
    request_id = request.headers.get("X-Request-ID")
    if request_id and len(request_id) > 80:
        request_id = None
    factor = approve_emission_factor(
        db,
        tenant_id=tenant.tenant_id,
        reviewer_user_id=tenant.user_id,
        factor_id=factor_id,
        note=payload.note,
        request_id=request_id,
    )
    return {
        "id": factor.id,
        "code": factor.code,
        "name": factor.name,
        "value_kgco2e": str(factor.value_kgco2e),
        "numerator_unit": factor.numerator_unit,
        "denominator_unit": factor.denominator_unit,
        "activity_category": factor.activity_category,
        "methodology": factor.methodology,
        "geography": factor.geography,
        "source_name": factor.source_name,
        "source_url": factor.source_url,
        "source_year": factor.source_year,
        "version": factor.version,
        "approval_status": factor.approval_status,
        "approved_by": factor.approved_by,
        "approved_at": factor.approved_at.isoformat() if factor.approved_at else None,
        "approval_note": factor.approval_note,
    }
