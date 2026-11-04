"""Transactional persistence for preliminary ESG inventory calculations.

User-submitted factors are stored as pending and are never promoted to approved
factors automatically. A persisted calculation is explicitly marked pending
human review; it is not an assurance-ready or regulatory filing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ActivityRecord,
    AuditEvent,
    CalculationSnapshot,
    EmissionFactor,
    Tenant,
)
from .schemas import InventoryCalculationRequest, InventoryCalculationResult

ENGINE_VERSION = "0.4.0"
METHODOLOGY_VERSION = "user-submitted-factor-preview-v1"


def _digest(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def persist_inventory_calculation(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    request: InventoryCalculationRequest,
    result: InventoryCalculationResult,
    request_id: str | None = None,
) -> UUID:
    """Persist factors, activity records, immutable snapshot and audit trail atomically."""
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        raise ValueError("Authorized tenant does not exist")

    factor_cache: dict[str, EmissionFactor] = {}
    for item in request.records:
        factor_identity = {
            "category": item.category,
            "unit": item.factor_unit.strip().lower(),
            "source": item.factor_source_name.strip(),
            "url": str(item.factor_source_url),
            "year": item.factor_year,
            "version": item.factor_version,
        }
        factor_code = "USR-" + _digest(factor_identity)[:60]
        cache_key = factor_code + ":" + item.factor_version
        factor = factor_cache.get(cache_key)
        if factor is None:
            factor = db.scalar(
                select(EmissionFactor).where(
                    EmissionFactor.tenant_id == tenant_id,
                    EmissionFactor.code == factor_code,
                    EmissionFactor.version == item.factor_version,
                )
            )
            if factor is None:
                factor = EmissionFactor(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    code=factor_code,
                    name=f"{item.category}: {item.factor_source_name}"[:200],
                    value_kgco2e=item.emission_factor_kgco2e_per_unit,
                    numerator_unit="kgCO2e",
                    denominator_unit=item.factor_unit,
                    geography=tenant.country_code,
                    source_name=item.factor_source_name,
                    source_url=str(item.factor_source_url),
                    source_year=item.factor_year,
                    version=item.factor_version,
                    methodology="user_submitted_pending_human_review",
                    activity_category=item.category,
                    valid_from=datetime.combine(
                        request.reporting_period_start, time.min, tzinfo=timezone.utc
                    ),
                    approval_status="pending",
                )
                db.add(factor)
                db.flush()
                db.add(AuditEvent(
                    tenant_id=tenant_id,
                    actor_user_id=user_id,
                    action="emission_factor.submitted",
                    entity_type="emission_factor",
                    entity_id=str(factor.id),
                    after_state={
                        "code": factor.code,
                        "version": factor.version,
                        "approval_status": "pending",
                        "source_url": factor.source_url,
                    },
                    request_id=request_id,
                ))
            elif (
                factor.value_kgco2e != item.emission_factor_kgco2e_per_unit
                or factor.denominator_unit.strip().lower() != item.factor_unit.strip().lower()
                or factor.source_url != str(item.factor_source_url)
                or factor.source_year != item.factor_year
                or factor.source_name != item.factor_source_name
            ):
                raise ValueError(
                    "A factor with the same provenance key already exists with different contents"
                )
            factor_cache[cache_key] = factor

        activity = ActivityRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            created_by=user_id,
            name=item.name,
            scope=item.scope,
            category=item.category,
            amount=item.activity_amount,
            unit=item.activity_unit,
            period_start=request.reporting_period_start,
            period_end=request.reporting_period_end,
            factor_id=factor.id,
            data_quality="unreviewed",
        )
        db.add(activity)
        db.flush()
        db.add(AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="activity_record.created",
            entity_type="activity_record",
            entity_id=str(activity.id),
            after_state={
                "scope": activity.scope,
                "category": activity.category,
                "amount": str(activity.amount),
                "unit": activity.unit,
                "data_quality": "unreviewed",
                "factor_id": str(factor.id),
            },
            request_id=request_id,
        ))

    request_payload = request.model_dump(mode="json")
    input_digest = _digest(request_payload)
    snapshot_id = uuid4()
    result_payload = result.model_dump(mode="json")
    result_payload["review_status"] = "pending_review"
    result_payload["input_digest"] = input_digest
    snapshot = CalculationSnapshot(
        id=snapshot_id,
        tenant_id=tenant_id,
        created_by=user_id,
        period_start=request.reporting_period_start,
        period_end=request.reporting_period_end,
        methodology_version=METHODOLOGY_VERSION,
        engine_version=ENGINE_VERSION,
        input_digest=input_digest,
        result_payload=result_payload,
    )
    db.add(snapshot)
    db.flush()
    db.add(AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="calculation_snapshot.created",
        entity_type="calculation_snapshot",
        entity_id=str(snapshot_id),
        after_state={
            "input_digest": input_digest,
            "methodology_version": METHODOLOGY_VERSION,
            "engine_version": ENGINE_VERSION,
            "review_status": "pending_review",
        },
        request_id=request_id,
    ))
    db.commit()
    return snapshot_id
