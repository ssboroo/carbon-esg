"""Tenant-scoped emission-factor submission and immutable human review."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import get_current_user
from .dependencies import get_db_session
from .factor_schemas import EmissionFactorCreate, FactorReviewDecision, FactorReviewQueueItem
from .factor_status import factor_approval_status
from .inventories import _require_membership
from .models import AuditEvent, EmissionFactor, EmissionFactorReview

router = APIRouter(
    prefix="/v1/organizations/{organization_id}/emission-factors",
    tags=["emission-factor-review"],
)
REVIEW_ROLES = {"owner", "admin"}


def _require_independent_reviewer(submitted_by_subject: str | None, reviewer_subject: str) -> None:
    """Enforce a four-eyes control: submitters cannot approve their own factor."""
    if not submitted_by_subject:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Коэффициентийн бүртгэгч тодорхойгүй тул дахин бүртгүүлэх шаардлагатай",
        )
    if submitted_by_subject == reviewer_subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Коэффициент бүртгэсэн хэрэглэгч өөрийн бүртгэлийг батлах боломжгүй",
        )


def _queue_item(factor: EmissionFactor, review: EmissionFactorReview | None) -> FactorReviewQueueItem:
    return FactorReviewQueueItem(
        id=factor.id,
        factor_code=factor.factor_code,
        name=factor.name,
        scope=factor.scope,
        scope_2_method=factor.scope_2_method,
        category=factor.category,
        factor_value=factor.factor_value,
        factor_unit=factor.factor_unit,
        gas_basis=factor.gas_basis,
        source_name=factor.source_name,
        source_url=factor.source_url,
        source_document=factor.source_document,
        factor_year=factor.factor_year,
        version=factor.version,
        geography_code=factor.geography_code,
        geography_name=factor.geography_name,
        geography_boundary=factor.geography_boundary,
        valid_from=factor.valid_from,
        valid_to=factor.valid_to,
        approval_status=factor_approval_status(factor, review.decision if review else None),
        submitted_by_subject=factor.submitted_by_subject,
        reviewer_subject=review.reviewer_subject if review else None,
        reviewed_at=review.reviewed_at if review else None,
        review_note=review.review_note if review else None,
        created_at=factor.created_at,
    )


@router.post("", response_model=FactorReviewQueueItem, status_code=status.HTTP_201_CREATED)
def submit_emission_factor(
    organization_id: uuid.UUID,
    request: EmissionFactorCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FactorReviewQueueItem:
    factor_id = uuid.uuid4()
    try:
        with db.begin():
            _require_membership(db, user["sub"], organization_id, write=True)
            factor = EmissionFactor(
                id=factor_id,
                organization_id=organization_id,
                factor_code=request.factor_code,
                name=request.name,
                scope=request.scope,
                scope_2_method=request.scope_2_method,
                category=request.category,
                factor_value=request.factor_value,
                factor_unit=request.factor_unit,
                gas_basis=request.gas_basis,
                source_name=request.source_name,
                source_url=str(request.source_url),
                source_document=request.source_document,
                factor_year=request.factor_year,
                version=request.version,
                geography_code=request.geography_code,
                geography_name=request.geography_name,
                geography_boundary=request.geography_boundary,
                valid_from=request.valid_from,
                valid_to=request.valid_to,
                verified=False,
                submitted_by_subject=user["sub"],
            )
            db.add(factor)
            db.flush()
            db.add(
                AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user["sub"],
                    action="emission_factor.submitted",
                    entity_type="emission_factor",
                    entity_id=str(factor_id),
                    details={
                        "factor_code": factor.factor_code,
                        "version": factor.version,
                        "scope": factor.scope,
                        "scope_2_method": factor.scope_2_method,
                        "category": factor.category,
                        "factor_value": str(factor.factor_value),
                        "factor_unit": factor.factor_unit,
                        "gas_basis": factor.gas_basis,
                        "source_name": factor.source_name,
                        "source_url": factor.source_url,
                        "factor_year": factor.factor_year,
                        "geography_code": factor.geography_code,
                        "geography_name": factor.geography_name,
                        "geography_boundary": factor.geography_boundary,
                        "valid_from": factor.valid_from.isoformat() if factor.valid_from else None,
                        "valid_to": factor.valid_to.isoformat() if factor.valid_to else None,
                    },
                )
            )
            db.flush()
            db.refresh(factor)
        return _queue_item(factor, None)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ижил код болон хувилбартай коэффициент аль хэдийн бүртгэгдсэн байна",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Коэффициент бүртгэх боломжгүй байна",
        ) from exc


@router.get("/review-queue", response_model=list[FactorReviewQueueItem])
def list_factor_review_queue(
    organization_id: uuid.UUID,
    approval_status: Literal["pending", "approved", "rejected", "all"] = Query(default="pending"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[FactorReviewQueueItem]:
    try:
        with db.begin():
            membership = _require_membership(db, user["sub"], organization_id)
            if membership.role not in REVIEW_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Коэффициентийн хяналтын жагсаалтыг owner эсвэл admin эрхтэй хэрэглэгч харна",
                )
            statement = (
                select(EmissionFactor, EmissionFactorReview)
                .outerjoin(
                    EmissionFactorReview,
                    (EmissionFactorReview.organization_id == EmissionFactor.organization_id)
                    & (EmissionFactorReview.emission_factor_id == EmissionFactor.id),
                )
                .where(EmissionFactor.organization_id == organization_id)
                .order_by(EmissionFactor.created_at.desc(), EmissionFactor.id.asc())
                .limit(200)
            )
            if approval_status == "pending":
                statement = statement.where(
                    EmissionFactor.verified.is_(False),
                    EmissionFactorReview.id.is_(None),
                )
            elif approval_status == "approved":
                statement = statement.where(
                    or_(
                        EmissionFactor.verified.is_(True),
                        EmissionFactorReview.decision == "approved",
                    )
                )
            elif approval_status == "rejected":
                statement = statement.where(EmissionFactorReview.decision == "rejected")
            rows = db.execute(statement).all()
            return [_queue_item(factor, review) for factor, review in rows]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Коэффициентийн хяналтын жагсаалт түр боломжгүй байна",
        ) from exc


@router.post("/{factor_id}/review", response_model=FactorReviewQueueItem)
def review_emission_factor(
    organization_id: uuid.UUID,
    factor_id: uuid.UUID,
    request: FactorReviewDecision,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FactorReviewQueueItem:
    try:
        with db.begin():
            membership = _require_membership(db, user["sub"], organization_id)
            if membership.role not in REVIEW_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Коэффициент батлах эсвэл буцаахад owner/admin эрх шаардлагатай",
                )
            factor = db.scalar(
                select(EmissionFactor)
                .where(
                    EmissionFactor.id == factor_id,
                    EmissionFactor.organization_id == organization_id,
                )
                .with_for_update()
            )
            if factor is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Коэффициент олдсонгүй",
                )
            if factor.verified:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Энэ коэффициент өмнө нь баталгаажсан бөгөөд өөрчлөх боломжгүй",
                )
            if factor.geography_code == "LEGACY_UNSPECIFIED" or factor.valid_from is None or factor.valid_to is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Хуучин коэффициентийн газарзүй эсвэл хүчинтэй хугацаа тодорхойгүй тул бүрэн metadata-тай шинэ хувилбар бүртгэнэ үү",
                )
            if factor.scope == "scope_2" and factor.scope_2_method not in {"location_based", "market_based"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Хуучин Scope 2 коэффициентэд аргачлал тодорхойгүй байна; location-based эсвэл market-based гэж шинэ хувилбараар дахин бүртгэнэ үү",
                )
            _require_independent_reviewer(factor.submitted_by_subject, user["sub"])
            existing_review = db.scalar(
                select(EmissionFactorReview).where(
                    EmissionFactorReview.organization_id == organization_id,
                    EmissionFactorReview.emission_factor_id == factor_id,
                )
            )
            if existing_review is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Энэ коэффициентэд шийдвэр аль хэдийн бүртгэгдсэн; шинэ хувилбар үүсгэнэ үү",
                )

            review = EmissionFactorReview(
                id=uuid.uuid4(),
                organization_id=organization_id,
                emission_factor_id=factor_id,
                decision=request.decision,
                reviewer_subject=user["sub"],
                review_note=request.note,
            )
            db.add(review)
            db.flush()
            db.add(
                AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user["sub"],
                    action=f"emission_factor.{request.decision}",
                    entity_type="emission_factor",
                    entity_id=str(factor_id),
                    details={
                        "factor_code": factor.factor_code,
                        "version": factor.version,
                        "decision": request.decision,
                        "review_note": request.note,
                        "source_name": factor.source_name,
                        "source_url": factor.source_url,
                        "factor_year": factor.factor_year,
                        "geography_code": factor.geography_code,
                        "geography_name": factor.geography_name,
                        "geography_boundary": factor.geography_boundary,
                        "valid_from": factor.valid_from.isoformat() if factor.valid_from else None,
                        "valid_to": factor.valid_to.isoformat() if factor.valid_to else None,
                    },
                )
            )
            db.flush()
            db.refresh(review)
        return _queue_item(factor, review)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Коэффициентийн шийдвэр давхар бүртгэгдсэн; шинэ хувилбар үүсгэнэ үү",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Коэффициентийн шийдвэр хадгалах боломжгүй байна",
        ) from exc
