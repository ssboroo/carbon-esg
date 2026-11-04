import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .calculator import calculate_inventory
from .database import engine, get_db
from .auth import TenantContext, require_roles
from .persistence import persist_inventory_calculation
from .approved_calculation import calculate_and_persist_approved
from .schemas import ApprovedInventoryCalculationRequest, InventoryCalculationRequest, InventoryCalculationResult
from .factor_routes import router as emission_factor_router
from .activity_routes import router as activity_record_router
from .evidence_routes import router as evidence_router
from .scope3_routes import router as scope3_router
from .evidence_vault import check_evidence_dependencies

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

if IS_PRODUCTION and not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is required when ENVIRONMENT=production")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "" if IS_PRODUCTION else "http://localhost:3000",
    ).split(",")
    if origin.strip()
]
if "*" in cors_origins:
    raise RuntimeError("CORS_ORIGINS must contain explicit trusted origins, not '*'.")
if IS_PRODUCTION and not cors_origins:
    raise RuntimeError("CORS_ORIGINS must contain at least one trusted origin in production.")
if IS_PRODUCTION and not all(os.getenv(key) for key in ("OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL")):
    raise RuntimeError("OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL are required in production.")
if IS_PRODUCTION and not all(os.getenv(key) for key in ("S3_ENDPOINT_URL", "S3_REGION", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "CLAMAV_HOST")):
    raise RuntimeError("Private S3 storage and ClamAV configuration are required in production.")

app = FastAPI(
    title="Carbon ESG API",
    version="0.4.0",
    description="API for auditable organizational greenhouse-gas accounting.",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-Request-ID"],
)


@app.middleware("http")
async def security_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Liveness only: confirms the process is responding."""
    return {"status": "ok", "service": "carbon-esg-api", "version": "0.4.0"}


@app.get("/ready", tags=["operations"])
def readiness_check() -> dict[str, str]:
    """Readiness: requires database connectivity and an applied Alembic revision."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            if not revision:
                raise HTTPException(
                    status_code=503, detail="Database migrations have not been applied"
                )
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database is not ready") from None
    if IS_PRODUCTION:
        check_evidence_dependencies()
    return {"status": "ready", "database": "connected", "migration": revision, "evidence_storage": "ready" if IS_PRODUCTION else "not_required_in_development"}


@app.get("/", tags=["operations"])
def root() -> dict[str, str]:
    return {"name": "Carbon ESG API", "version": "0.4.0"}


@app.post(
    "/v1/calculations",
    response_model=InventoryCalculationResult,
    summary="Persist a preliminary Scope 1 and Scope 2 inventory calculation",
    tags=["calculations"],
)
def create_calculation(
    payload: InventoryCalculationRequest,
    http_request: Request,
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> InventoryCalculationResult:
    """Calculate deterministically and atomically persist all provenance and audit data.

    Submitted emission factors remain pending human review. The response is not
    an approved inventory or assurance-ready statement.
    """
    result = calculate_inventory(payload)
    request_id = http_request.headers.get("X-Request-ID")
    if request_id and len(request_id) > 80:
        request_id = None
    try:
        snapshot_id = persist_inventory_calculation(
            db,
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            request=payload,
            result=result,
            request_id=request_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Calculation could not be persisted; no result was committed",
        ) from None

    return result.model_copy(
        update={"snapshot_id": snapshot_id, "review_status": "pending_review"}
    )


@app.post(
    "/v1/calculations/approved",
    response_model=InventoryCalculationResult,
    summary="Calculate using approved tenant emission factors",
    tags=["calculations"],
)
def create_approved_calculation(
    payload: ApprovedInventoryCalculationRequest,
    http_request: Request,
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> InventoryCalculationResult:
    """Calculate using only approved, tenant-owned, in-period registry factors.

    The factor provenance is approved; activity evidence and the resulting
    inventory snapshot remain pending independent human review.
    """
    request_id = http_request.headers.get("X-Request-ID")
    if request_id and len(request_id) > 80:
        request_id = None
    try:
        return calculate_and_persist_approved(
            db,
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
            payload=payload,
            request_id=request_id,
        )
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Approved-factor calculation could not be persisted; no result was committed",
        ) from None


@app.get("/v1/me", tags=["identity"])
def current_user(tenant: TenantContext = Depends(require_roles("owner", "admin", "manager", "reviewer", "viewer"))):
    return {
        "user_id": str(tenant.user_id),
        "tenant_id": str(tenant.tenant_id),
        "role": tenant.role,
    }


from .legal_routes import router as legal_registry_router

app.include_router(legal_registry_router)
app.include_router(emission_factor_router)
app.include_router(activity_record_router)
app.include_router(evidence_router)
app.include_router(scope3_router)
