"""Human-governed emission-factor review and approval."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent, EmissionFactor


def approve_emission_factor(
    db: Session,
    *,
    tenant_id: UUID,
    reviewer_user_id: UUID,
    factor_id: UUID,
    note: str,
    request_id: str | None = None,
) -> EmissionFactor:
    """Approve one pending factor in the current tenant, with an audit event."""
    normalized_note = note.strip()
    if len(normalized_note) < 10:
        raise HTTPException(status_code=422, detail="Reviewer note must contain at least 10 characters")

    factor = db.scalar(
        select(EmissionFactor)
        .where(
            EmissionFactor.id == factor_id,
            EmissionFactor.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if factor is None:
        raise HTTPException(status_code=404, detail="Emission factor not found")
    if factor.approval_status != "pending":
        raise HTTPException(status_code=409, detail="Only pending emission factors can be approved")

    before_state = {
        "approval_status": factor.approval_status,
        "code": factor.code,
        "version": factor.version,
        "source_name": factor.source_name,
        "source_url": factor.source_url,
        "source_year": factor.source_year,
        "value_kgco2e": str(factor.value_kgco2e),
        "denominator_unit": factor.denominator_unit,
    }
    now = datetime.now(timezone.utc)
    factor.approval_status = "approved"
    factor.approved_by = reviewer_user_id
    factor.approved_at = now
    factor.approval_note = normalized_note
    db.add(AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=reviewer_user_id,
        action="emission_factor.approved",
        entity_type="emission_factor",
        entity_id=str(factor.id),
        before_state=before_state,
        after_state={
            **before_state,
            "approval_status": "approved",
            "approved_by": str(reviewer_user_id),
            "approved_at": now.isoformat(),
            "approval_note": normalized_note,
        },
        request_id=request_id,
    ))
    db.commit()
    db.refresh(factor)
    return factor
