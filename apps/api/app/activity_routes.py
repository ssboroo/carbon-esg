"""Tenant-scoped persisted activity-record read API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import TenantContext, require_roles
from .database import get_db
from .models import ActivityRecord, EmissionFactor

router = APIRouter(prefix="/v1/activity-records", tags=["activity-records"])


class ActivityRecordResponse(BaseModel):
    id: UUID
    name: str
    scope: str
    category: str
    scope_2_basis: str | None
    amount: Decimal
    unit: str
    emissions_kgco2e: Decimal
    emissions_tco2e: Decimal
    factor_id: UUID
    factor_code: str
    factor_value_kgco2e: Decimal
    factor_unit: str
    factor_source_name: str
    factor_source_url: str
    factor_year: int
    factor_version: str
    factor_approval_status: str
    data_quality: str
    period_start: date
    period_end: date
    created_at: str


@router.get("", response_model=list[ActivityRecordResponse])
def list_activity_records(
    period_start: date | None = None,
    period_end: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager", "reviewer", "viewer")),
    db: Session = Depends(get_db),
):
    query = (
        select(ActivityRecord, EmissionFactor)
        .join(EmissionFactor, EmissionFactor.id == ActivityRecord.factor_id)
        .where(ActivityRecord.tenant_id == tenant.tenant_id)
    )
    if period_start:
        query = query.where(ActivityRecord.period_end >= period_start)
    if period_end:
        query = query.where(ActivityRecord.period_start <= period_end)
    rows = db.execute(
        query.order_by(ActivityRecord.created_at.desc(), ActivityRecord.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    response = []
    for activity, factor in rows:
        emissions_kg = activity.amount * factor.value_kgco2e
        response.append({
            "id": activity.id,
            "name": activity.name,
            "scope": activity.scope,
            "category": activity.category,
            "scope_2_basis": activity.scope_2_basis,
            "amount": activity.amount,
            "unit": activity.unit,
            "emissions_kgco2e": emissions_kg,
            "emissions_tco2e": emissions_kg / Decimal("1000"),
            "factor_id": factor.id,
            "factor_code": factor.code,
            "factor_value_kgco2e": factor.value_kgco2e,
            "factor_unit": factor.denominator_unit,
            "factor_source_name": factor.source_name,
            "factor_source_url": factor.source_url,
            "factor_year": factor.source_year,
            "factor_version": factor.version,
            "factor_approval_status": factor.approval_status,
            "data_quality": activity.data_quality,
            "period_start": activity.period_start,
            "period_end": activity.period_end,
            "created_at": activity.created_at.isoformat(),
        })
    return response
