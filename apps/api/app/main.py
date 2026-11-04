import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .calculator import calculate_inventory
from .database import engine
from .auth import TenantContext, get_current_membership
from .schemas import InventoryCalculationRequest, InventoryCalculationResult

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
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
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
        # Do not return connection strings, SQL, or database internals.
        raise HTTPException(status_code=503, detail="Database is not ready") from None
    return {"status": "ready", "database": "connected", "migration": revision}


@app.get("/", tags=["operations"])
def root() -> dict[str, str]:
    return {"name": "Carbon ESG API", "version": "0.4.0"}


@app.post(
    "/v1/calculations",
    response_model=InventoryCalculationResult,
    summary="Calculate an auditable Scope 1 and Scope 2 inventory",
    tags=["calculations"],
)
def create_calculation(
    request: InventoryCalculationRequest,
    tenant: TenantContext = __import__("fastapi").Depends(get_current_membership),
) -> InventoryCalculationResult:
    # Tenant authorization is required even while this endpoint remains a stateless preview.
    return calculate_inventory(request)


@app.get("/v1/me", tags=["identity"])
def current_user(tenant: TenantContext = __import__("fastapi").Depends(get_current_membership)):
    return {
        "user_id": str(tenant.user_id),
        "tenant_id": str(tenant.tenant_id),
        "role": tenant.role,
    }


from .legal_routes import router as legal_registry_router

app.include_router(legal_registry_router)
