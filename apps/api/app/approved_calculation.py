"""Authoritative calculations using only approved tenant emission factors."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .calculator import calculate_inventory
from .models import ActivityRecord, AuditEvent, CalculationSnapshot, EmissionFactor
from .schemas import (
    ApprovedInventoryCalculationRequest,
    InventoryCalculationRequest,
    InventoryCalculationResult,
)


def _canonical_digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_method(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def resolve_approved_calculation(
    db: Session,
    *,
    tenant_id: UUID,
    payload: ApprovedInventoryCalculationRequest,
) -> tuple[InventoryCalculationRequest, dict[UUID, EmissionFactor]]:
    """Resolve factors under tenant scope and reject unapproved or mismatched inputs."""
    factor_ids = {record.factor_id for record in payload.records}
    factors = db.scalars(
        select(EmissionFactor)
        .where(
            EmissionFactor.tenant_id == tenant_id,
            EmissionFactor.id.in_(factor_ids),
        )
        .with_for_update()
    ).all()
    by_id = {factor.id: factor for factor in factors}
    if set(by_id) != factor_ids:
        raise HTTPException(status_code=422, detail="One or more emission factors are not available in this organization")

    resolved_records = []
    for item in payload.records:
        factor = by_id[item.factor_id]
        if factor.approval_status != "approved" or factor.approved_by is None or factor.approved_at is None:
            raise HTTPException(status_code=409, detail=f"Emission factor {factor.code} is not approved")
        if factor.activity_category != item.category:
            raise HTTPException(status_code=422, detail=f"Emission factor {factor.code} is not approved for category {item.category}")
        if factor.denominator_unit.strip().lower() != item.activity_unit.strip().lower():
            raise HTTPException(status_code=422, detail=f"Activity unit does not match factor {factor.code}")
        if factor.valid_from.date() > payload.reporting_period_start:
            raise HTTPException(status_code=422, detail=f"Emission factor {factor.code} is not valid at the start of the reporting period")
        if factor.valid_to is not None and factor.valid_to.date() < payload.reporting_period_end:
            raise HTTPException(status_code=422, detail=f"Emission factor {factor.code} expires before the reporting period ends")
        if item.scope == "scope_2":
            expected = _normalize_method(item.scope_2_basis or "")
            actual = _normalize_method(factor.methodology)
            if actual != expected:
                raise HTTPException(status_code=422, detail=f"Scope 2 factor {factor.code} methodology does not match {expected}")

        resolved_records.append({
            "name": item.name,
            "scope": item.scope,
            "category": item.category,
            "activity_amount": str(item.activity_amount),
            "activity_unit": item.activity_unit,
            "emission_factor_kgco2e_per_unit": str(factor.value_kgco2e),
            "factor_unit": factor.denominator_unit,
            "factor_source_name": factor.source_name,
            "factor_source_url": factor.source_url,
            "factor_year": factor.source_year,
            "factor_version": factor.version,
            "scope_2_basis": item.scope_2_basis,
        })

    calculation_request = InventoryCalculationRequest.model_validate({
        "reporting_period_start": payload.reporting_period_start,
        "reporting_period_end": payload.reporting_period_end,
        "records": resolved_records,
    })
    return calculation_request, by_id


def persist_approved_calculation(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    submitted: ApprovedInventoryCalculationRequest,
    calculation_request: InventoryCalculationRequest,
    result: InventoryCalculationResult,
    factors: dict[UUID, EmissionFactor],
    request_id: str | None = None,
) -> UUID:
    """Persist approved-factor activities, snapshot and audit data atomically."""
    digest_payload = submitted.model_dump(mode="json")
    digest_payload["factor_provenance"] = [
        {
            "factor_id": str(f.id),
            "code": f.code,
            "version": f.version,
            "value_kgco2e": str(f.value_kgco2e),
            "source_url": f.source_url,
            "source_year": f.source_year,
            "source_name": f.source_name,
            "geography": f.geography,
            "activity_category": f.activity_category,
            "denominator_unit": f.denominator_unit,
            "methodology": f.methodology,
            "valid_from": f.valid_from.isoformat(),
            "valid_to": f.valid_to.isoformat() if f.valid_to else None,
            "approval_note": f.approval_note,
            "approved_by": str(f.approved_by),
            "approved_at": f.approved_at.isoformat() if f.approved_at else None,
        }
        for f in sorted(factors.values(), key=lambda item: str(item.id))
    ]
    input_digest = _canonical_digest(digest_payload)

    for item in submitted.records:
        factor = factors[item.factor_id]
        activity = ActivityRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            created_by=user_id,
            name=item.name,
            scope=item.scope,
            category=item.category,
            scope_2_basis=item.scope_2_basis,
            amount=item.activity_amount,
            unit=item.activity_unit,
            period_start=submitted.reporting_period_start,
            period_end=submitted.reporting_period_end,
            factor_id=factor.id,
            data_quality="unreviewed",
        )
        db.add(activity)
        db.flush()
        db.add(AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="activity_record.created_from_approved_factor",
            entity_type="activity_record",
            entity_id=str(activity.id),
            after_state={
                "scope": activity.scope,
                "category": activity.category,
                "amount": str(activity.amount),
                "unit": activity.unit,
                "factor_id": str(factor.id),
                "factor_version": factor.version,
                "factor_approval_status": "approved",
                "scope_2_basis": item.scope_2_basis,
                "data_quality": "unreviewed",
            },
            request_id=request_id,
        ))

    snapshot_id = uuid4()
    result_payload = result.model_dump(mode="json")
    result_payload["review_status"] = "pending_review"
    result_payload["factor_status"] = "approved"
    result_payload["input_digest"] = input_digest
    snapshot = CalculationSnapshot(
        id=snapshot_id,
        tenant_id=tenant_id,
        created_by=user_id,
        period_start=submitted.reporting_period_start,
        period_end=submitted.reporting_period_end,
        methodology_version="approved-factor-registry-v1",
        engine_version="0.4.0",
        input_digest=input_digest,
        result_payload=result_payload,
    )
    db.add(snapshot)
    db.flush()
    db.add(AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="calculation_snapshot.created_from_approved_factors",
        entity_type="calculation_snapshot",
        entity_id=str(snapshot_id),
        after_state={
            "input_digest": input_digest,
            "methodology_version": snapshot.methodology_version,
            "engine_version": snapshot.engine_version,
            "factor_status": "approved",
            "inventory_review_status": "pending_review",
        },
        request_id=request_id,
    ))
    db.commit()
    return snapshot_id


def calculate_and_persist_approved(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    payload: ApprovedInventoryCalculationRequest,
    request_id: str | None = None,
) -> InventoryCalculationResult:
    calculation_request, factors = resolve_approved_calculation(
        db, tenant_id=tenant_id, payload=payload
    )
    result = calculate_inventory(calculation_request)
    snapshot_id = persist_approved_calculation(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        submitted=payload,
        calculation_request=calculation_request,
        result=result,
        factors=factors,
        request_id=request_id,
    )
    return result.model_copy(update={
        "snapshot_id": snapshot_id,
        "review_status": "pending_review",
        "factor_status": "approved",
    })
