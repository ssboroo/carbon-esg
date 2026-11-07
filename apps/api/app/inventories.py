"""Tenant-protected inventory, activity and immutable calculation endpoints."""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import set_identity_context, set_tenant_context
from .dependencies import get_db_session
from .inventory_schemas import (
    ActivityRecordCreate,
    ActivityRecordSummary,
    CalculationRunSummary,
    EmissionFactorSummary,
    InventoryCreate,
    InventorySummary,
)
from .models import (
    ActivityRecord,
    AuditEvent,
    CalculationRun,
    EmissionFactor,
    EmissionFactorReview,
    Inventory,
    OrganizationMembership,
)
from .schemas import SCOPE_1_CATEGORIES, SCOPE_2_CATEGORIES
from .factor_status import factor_approval_status, is_factor_approved

router = APIRouter(
    prefix="/v1/organizations/{organization_id}/inventories",
    tags=["inventories"],
)
factor_router = APIRouter(
    prefix="/v1/organizations/{organization_id}/emission-factors",
    tags=["emission-factors"],
)

WRITE_ROLES = {"owner", "admin", "editor"}
EIGHT_PLACES = Decimal("0.00000001")
METHODOLOGY_VERSION = "scope12-v1.0.0"


def calculate_activity_emissions(activity_amount: Decimal, factor_value: Decimal) -> Decimal:
    """Return kgCO2e using Decimal arithmetic and the stored factor value."""
    return (activity_amount * factor_value).quantize(
        EIGHT_PLACES,
        rounding=ROUND_HALF_UP,
    )


def activity_snapshot_is_valid(
    record: ActivityRecord,
    factor: EmissionFactor,
    review_decision: str | None = None,
) -> bool:
    """Validate the immutable activity/factor snapshot and its approval state."""
    factor_unit = factor.factor_unit.strip()
    return (
        is_factor_approved(factor, review_decision)
        and factor.scope == record.scope
        and factor.category == record.category
        and factor.gas_basis.strip().casefold() == "co2e"
        and factor_unit == record.activity_unit == record.factor_unit_snapshot
        and factor.factor_value == record.factor_value_snapshot
        and calculate_activity_emissions(
            record.activity_amount,
            record.factor_value_snapshot,
        ) == record.emissions_kgco2e
    )


def _require_membership(
    db: Session,
    user_subject: str,
    organization_id: uuid.UUID,
    *,
    write: bool = False,
) -> OrganizationMembership:
    """Establish identity first, then tenant context after membership is proven."""
    set_identity_context(db, user_subject)
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_subject == user_subject,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Байгууллага олдсонгүй эсвэл танд хандах эрх байхгүй",
        )
    if write and membership.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Энэ үйлдэлд засварлах эрх шаардлагатай",
        )
    set_tenant_context(db, str(organization_id))
    return membership


def _get_inventory(
    db: Session,
    organization_id: uuid.UUID,
    inventory_id: uuid.UUID,
) -> Inventory:
    inventory = db.scalar(
        select(Inventory).where(
            Inventory.id == inventory_id,
            Inventory.organization_id == organization_id,
        )
    )
    if inventory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тайлант бүртгэл олдсонгүй",
        )
    return inventory


def _activity_summary(record: ActivityRecord, factor: EmissionFactor) -> ActivityRecordSummary:
    return ActivityRecordSummary(
        id=record.id,
        name=record.name,
        scope=record.scope,
        category=record.category,
        activity_amount=record.activity_amount,
        activity_unit=record.activity_unit,
        emission_factor_id=record.emission_factor_id,
        factor_value_snapshot=record.factor_value_snapshot,
        factor_unit_snapshot=record.factor_unit_snapshot,
        factor_code=factor.factor_code,
        factor_version=factor.version,
        factor_source_name=factor.source_name,
        factor_source_url=factor.source_url,
        factor_year=factor.factor_year,
        emissions_kgco2e=record.emissions_kgco2e,
    )


@factor_router.get("", response_model=list[EmissionFactorSummary])
def list_verified_emission_factors(
    organization_id: uuid.UUID,
    scope: Literal["scope_1", "scope_2"] | None = None,
    category: str | None = Query(default=None, max_length=64),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[EmissionFactorSummary]:
    """List only reviewed factors belonging to the authenticated organization."""
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id)
            statement = (
                select(EmissionFactor)
                .outerjoin(
                    EmissionFactorReview,
                    (EmissionFactorReview.organization_id == EmissionFactor.organization_id)
                    & (EmissionFactorReview.emission_factor_id == EmissionFactor.id),
                )
                .where(
                    EmissionFactor.organization_id == organization_id,
                    or_(
                        EmissionFactor.verified.is_(True),
                        EmissionFactorReview.decision == "approved",
                    ),
                )
                .order_by(
                    EmissionFactor.scope.asc(),
                    EmissionFactor.category.asc(),
                    EmissionFactor.factor_year.desc(),
                    EmissionFactor.factor_code.asc(),
                    EmissionFactor.version.desc(),
                )
            )
            if scope is not None:
                statement = statement.where(EmissionFactor.scope == scope)
            if category is not None:
                statement = statement.where(EmissionFactor.category == category)
            factors = db.scalars(statement).all()
            return [
                EmissionFactorSummary(
                    id=factor.id,
                    factor_code=factor.factor_code,
                    name=factor.name,
                    scope=factor.scope,
                    category=factor.category,
                    factor_value=factor.factor_value,
                    factor_unit=factor.factor_unit,
                    gas_basis=factor.gas_basis,
                    source_name=factor.source_name,
                    source_url=factor.source_url,
                    source_document=factor.source_document,
                    factor_year=factor.factor_year,
                    version=factor.version,
                    approval_status="approved",
                )
                for factor in factors
            ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ялгарлын коэффициентийн сан түр боломжгүй байна",
        ) from exc


@router.get("", response_model=list[InventorySummary])
def list_inventories(
    organization_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[InventorySummary]:
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id)
            rows = db.scalars(
                select(Inventory)
                .where(Inventory.organization_id == organization_id)
                .order_by(Inventory.reporting_period_start.desc(), Inventory.created_at.desc())
            ).all()
            return [
                InventorySummary(
                    id=row.id,
                    name=row.name,
                    reporting_period_start=row.reporting_period_start,
                    reporting_period_end=row.reporting_period_end,
                    status=row.status,
                )
                for row in rows
            ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Тайлант бүртгэлийн мэдээлэл түр боломжгүй байна",
        ) from exc


@router.post("", response_model=InventorySummary, status_code=status.HTTP_201_CREATED)
def create_inventory(
    organization_id: uuid.UUID,
    request: InventoryCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> InventorySummary:
    inventory_id = uuid.uuid4()
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id, write=True)
            inventory = Inventory(
                id=inventory_id,
                organization_id=organization_id,
                name=request.name,
                reporting_period_start=request.reporting_period_start,
                reporting_period_end=request.reporting_period_end,
                status="draft",
                created_by_subject=user["sub"],
            )
            db.add(inventory)
            db.flush()
            db.add(
                AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user["sub"],
                    action="inventory.created",
                    entity_type="inventory",
                    entity_id=str(inventory_id),
                    details={
                        "name": request.name,
                        "reporting_period_start": request.reporting_period_start.isoformat(),
                        "reporting_period_end": request.reporting_period_end.isoformat(),
                    },
                )
            )
        return InventorySummary(
            id=inventory_id,
            name=request.name,
            reporting_period_start=request.reporting_period_start,
            reporting_period_end=request.reporting_period_end,
            status="draft",
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тайлант бүртгэл үүсгэхэд өгөгдлийн зөрчил гарлаа",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Тайлант бүртгэл үүсгэх боломжгүй байна",
        ) from exc


@router.get("/{inventory_id}/activities", response_model=list[ActivityRecordSummary])
def list_activity_records(
    organization_id: uuid.UUID,
    inventory_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ActivityRecordSummary]:
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id)
            _get_inventory(db, organization_id, inventory_id)
            rows = db.execute(
                select(ActivityRecord, EmissionFactor)
                .join(
                    EmissionFactor,
                    (ActivityRecord.organization_id == EmissionFactor.organization_id)
                    & (ActivityRecord.emission_factor_id == EmissionFactor.id),
                )
                .where(
                    ActivityRecord.organization_id == organization_id,
                    ActivityRecord.inventory_id == inventory_id,
                )
                .order_by(ActivityRecord.created_at.asc(), ActivityRecord.id.asc())
            ).all()
            return [_activity_summary(record, factor) for record, factor in rows]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Үйл ажиллагааны мэдээлэл түр боломжгүй байна",
        ) from exc


@router.post(
    "/{inventory_id}/activities",
    response_model=ActivityRecordSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_activity_record(
    organization_id: uuid.UUID,
    inventory_id: uuid.UUID,
    request: ActivityRecordCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ActivityRecordSummary:
    record_id = uuid.uuid4()
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id, write=True)
            inventory = _get_inventory(db, organization_id, inventory_id)
            if inventory.status != "draft":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Зөвхөн ноорог тайланд үйл ажиллагааны мөр нэмэх боломжтой",
                )

            factor_row = db.execute(
                select(EmissionFactor, EmissionFactorReview.decision)
                .outerjoin(
                    EmissionFactorReview,
                    (EmissionFactorReview.organization_id == EmissionFactor.organization_id)
                    & (EmissionFactorReview.emission_factor_id == EmissionFactor.id),
                )
                .where(
                    EmissionFactor.id == request.emission_factor_id,
                    EmissionFactor.organization_id == organization_id,
                    or_(
                        EmissionFactor.verified.is_(True),
                        EmissionFactorReview.decision == "approved",
                    ),
                )
            ).first()
            factor = factor_row[0] if factor_row else None
            if factor is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Баталгаажсан, тухайн байгууллагад хамаарах ялгарлын коэффициент олдсонгүй",
                )

            allowed_categories = (
                SCOPE_1_CATEGORIES if request.scope == "scope_1" else SCOPE_2_CATEGORIES
            )
            if request.category not in allowed_categories:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Ангилал нь сонгосон хамрах хүрээнд тохирохгүй байна",
                )
            if factor.scope != request.scope or factor.category != request.category:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Ялгарлын коэффициентийн хамрах хүрээ эсвэл ангилал тохирохгүй байна",
                )
            if factor.gas_basis.strip().casefold() != "co2e":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Зөвхөн CO2e суурьтай баталгаажсан коэффициент ашиглана",
                )
            factor_unit = factor.factor_unit.strip()
            if factor_unit != request.activity_unit:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Үйл ажиллагааны нэгж коэффициентийн хуваарь нэгжтэй яг таарах ёстой",
                )

            emissions = calculate_activity_emissions(
                request.activity_amount,
                factor.factor_value,
            )
            record = ActivityRecord(
                id=record_id,
                organization_id=organization_id,
                inventory_id=inventory_id,
                emission_factor_id=factor.id,
                name=request.name,
                scope=request.scope,
                category=request.category,
                activity_amount=request.activity_amount,
                activity_unit=request.activity_unit,
                factor_value_snapshot=factor.factor_value,
                factor_unit_snapshot=factor_unit,
                emissions_kgco2e=emissions,
            )
            db.add(record)
            db.flush()
            db.add(
                AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user["sub"],
                    action="activity_record.created",
                    entity_type="activity_record",
                    entity_id=str(record_id),
                    details={
                        "inventory_id": str(inventory_id),
                        "scope": request.scope,
                        "category": request.category,
                        "activity_amount": str(request.activity_amount),
                        "activity_unit": request.activity_unit,
                        "factor_code": factor.factor_code,
                        "factor_version": factor.version,
                        "factor_value": str(factor.factor_value),
                        "factor_unit": factor_unit,
                        "factor_source_name": factor.source_name,
                        "factor_source_url": factor.source_url,
                        "factor_year": factor.factor_year,
                        "emissions_kgco2e": str(emissions),
                    },
                )
            )
        return _activity_summary(record, factor)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Үйл ажиллагааны мөр хадгалахад өгөгдлийн зөрчил гарлаа",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Үйл ажиллагааны мөр хадгалах боломжгүй байна",
        ) from exc


@router.post(
    "/{inventory_id}/calculate",
    response_model=CalculationRunSummary,
    status_code=status.HTTP_201_CREATED,
)
def calculate_persisted_inventory(
    organization_id: uuid.UUID,
    inventory_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> CalculationRunSummary:
    run_id = uuid.uuid4()
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id, write=True)
            _get_inventory(db, organization_id, inventory_id)
            rows = db.execute(
                select(ActivityRecord, EmissionFactor, EmissionFactorReview.decision)
                .join(
                    EmissionFactor,
                    (ActivityRecord.organization_id == EmissionFactor.organization_id)
                    & (ActivityRecord.emission_factor_id == EmissionFactor.id),
                )
                .outerjoin(
                    EmissionFactorReview,
                    (EmissionFactorReview.organization_id == EmissionFactor.organization_id)
                    & (EmissionFactorReview.emission_factor_id == EmissionFactor.id),
                )
                .where(
                    ActivityRecord.organization_id == organization_id,
                    ActivityRecord.inventory_id == inventory_id,
                )
                .order_by(ActivityRecord.created_at.asc(), ActivityRecord.id.asc())
            ).all()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Тооцоолохын өмнө үйл ажиллагааны мөр нэмнэ үү",
                )
            if any(
                not activity_snapshot_is_valid(record, factor, review_decision)
                for record, factor, review_decision in rows
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Үйл ажиллагааны мөр эсвэл коэффициентийн snapshot зөрүүтэй байна; тооцоолол зогслоо",
                )

            scope_1 = sum(
                (record.emissions_kgco2e for record, _factor, _review_decision in rows if record.scope == "scope_1"),
                Decimal("0"),
            ).quantize(EIGHT_PLACES, rounding=ROUND_HALF_UP)
            scope_2 = sum(
                (record.emissions_kgco2e for record, _factor, _review_decision in rows if record.scope == "scope_2"),
                Decimal("0"),
            ).quantize(EIGHT_PLACES, rounding=ROUND_HALF_UP)
            total = scope_1 + scope_2

            snapshot_records = []
            for record, factor, review_decision in rows:
                snapshot_records.append(
                    {
                        "activity_record_id": str(record.id),
                        "name": record.name,
                        "scope": record.scope,
                        "category": record.category,
                        "activity_amount": str(record.activity_amount),
                        "activity_unit": record.activity_unit,
                        "emission_factor_id": str(factor.id),
                        "factor_code": factor.factor_code,
                        "factor_value": str(record.factor_value_snapshot),
                        "factor_unit": record.factor_unit_snapshot,
                        "factor_gas_basis": factor.gas_basis,
                        "factor_source_name": factor.source_name,
                        "factor_source_url": factor.source_url,
                        "factor_source_document": factor.source_document,
                        "factor_year": factor.factor_year,
                        "factor_version": factor.version,
                        "factor_approval_status": factor_approval_status(factor, review_decision),
                        "emissions_kgco2e": str(record.emissions_kgco2e),
                    }
                )

            run = CalculationRun(
                id=run_id,
                organization_id=organization_id,
                inventory_id=inventory_id,
                scope_1_kgco2e=scope_1,
                scope_2_kgco2e=scope_2,
                total_kgco2e=total,
                methodology_version=METHODOLOGY_VERSION,
                input_snapshot={
                    "methodology": "emissions_kgco2e = activity_amount × factor_value_kgco2e_per_unit",
                    "rounding": "ROUND_HALF_UP to 8 decimal places in kgCO2e per activity record",
                    "records": snapshot_records,
                },
                calculated_by_subject=user["sub"],
            )
            db.add(run)
            db.flush()
            db.add(
                AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user["sub"],
                    action="inventory.calculated",
                    entity_type="calculation_run",
                    entity_id=str(run_id),
                    details={
                        "inventory_id": str(inventory_id),
                        "methodology_version": METHODOLOGY_VERSION,
                        "scope_1_kgco2e": str(scope_1),
                        "scope_2_kgco2e": str(scope_2),
                        "total_kgco2e": str(total),
                        "activity_record_count": len(rows),
                    },
                )
            )
            db.flush()
            db.refresh(run)
        return CalculationRunSummary(
            id=run_id,
            inventory_id=inventory_id,
            scope_1_kgco2e=scope_1,
            scope_2_kgco2e=scope_2,
            total_kgco2e=total,
            methodology_version=METHODOLOGY_VERSION,
            created_at=run.created_at,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тооцооллын snapshot хадгалахад өгөгдлийн зөрчил гарлаа",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Тооцоолол хадгалах боломжгүй байна",
        ) from exc


@router.get("/{inventory_id}/calculations", response_model=list[CalculationRunSummary])
def list_calculation_runs(
    organization_id: uuid.UUID,
    inventory_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[CalculationRunSummary]:
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id)
            _get_inventory(db, organization_id, inventory_id)
            rows = db.scalars(
                select(CalculationRun)
                .where(
                    CalculationRun.organization_id == organization_id,
                    CalculationRun.inventory_id == inventory_id,
                )
                .order_by(CalculationRun.created_at.desc(), CalculationRun.id.desc())
            ).all()
            return [
                CalculationRunSummary(
                    id=row.id,
                    inventory_id=row.inventory_id,
                    scope_1_kgco2e=row.scope_1_kgco2e,
                    scope_2_kgco2e=row.scope_2_kgco2e,
                    total_kgco2e=row.total_kgco2e,
                    methodology_version=row.methodology_version,
                    created_at=row.created_at,
                )
                for row in rows
            ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Тооцооллын түүх түр боломжгүй байна",
        ) from exc
