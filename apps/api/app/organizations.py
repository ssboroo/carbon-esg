"""Organization bootstrap endpoints with transaction-scoped PostgreSQL RLS context."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import get_current_user
from .db import set_identity_context, set_tenant_context
from .dependencies import get_db_session
from .models import AuditEvent, Organization, OrganizationMembership
from .organization_schemas import OrganizationCreate, OrganizationSummary

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationSummary])
def list_my_organizations(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[OrganizationSummary]:
    """List only organizations where the verified Neon Auth subject is a member."""
    try:
        with db.begin():
            set_identity_context(db, user["sub"])
            memberships = db.scalars(
                select(OrganizationMembership)
                .where(OrganizationMembership.user_subject == user["sub"])
                .order_by(OrganizationMembership.created_at.asc())
            ).all()

            organizations: list[OrganizationSummary] = []
            for membership in memberships:
                set_tenant_context(db, str(membership.organization_id))
                organization = db.get(Organization, membership.organization_id)
                if organization is not None:
                    organizations.append(
                        OrganizationSummary(
                            id=organization.id,
                            name=organization.name,
                            slug=organization.slug,
                            role=membership.role,
                        )
                    )
            return organizations
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Organization data is temporarily unavailable",
        ) from exc


@router.post("", response_model=OrganizationSummary, status_code=status.HTTP_201_CREATED)
def create_organization(
    request: OrganizationCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OrganizationSummary:
    """Create an organization and its initial owner membership atomically."""
    organization_id = uuid.uuid4()
    slug = request.slug or f"org-{organization_id.hex[:12]}"

    try:
        with db.begin():
            set_identity_context(db, user["sub"])
            set_tenant_context(db, str(organization_id))

            organization = Organization(
                id=organization_id,
                name=request.name,
                slug=slug,
            )
            db.add(organization)
            db.flush()

            membership = OrganizationMembership(
                organization_id=organization_id,
                user_subject=user["sub"],
                role="owner",
            )
            db.add(membership)
            db.add(
                AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user["sub"],
                    action="organization.created",
                    entity_type="organization",
                    entity_id=str(organization_id),
                    details={"slug": slug},
                )
            )
            db.flush()

        return OrganizationSummary(
            id=organization_id,
            name=request.name,
            slug=slug,
            role="owner",
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug is already in use",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Organization could not be created",
        ) from exc
