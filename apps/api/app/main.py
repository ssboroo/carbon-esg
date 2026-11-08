import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_user
from .calculator import calculate_inventory
from .schemas import InventoryCalculationRequest, InventoryCalculationResult

app = FastAPI(
    title="Carbon ESG API",
    version="0.3.0",
    description="API for auditable organizational greenhouse-gas accounting.",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
if not cors_origins or "*" in cors_origins:
    raise RuntimeError("CORS_ORIGINS must contain explicit trusted origins, not '*'.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "carbon-esg-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Carbon ESG API", "version": "0.3.0", "docs": "/docs"}


@app.get("/v1/auth/me", summary="Verify the current Neon Auth identity")
def current_identity(user: dict = Depends(get_current_user)) -> dict[str, str | None]:
    """Return minimal verified identity; tenant access still requires membership checks."""
    return {
        "subject": user["sub"],
        "email": user.get("email"),
        "name": user.get("name"),
    }


@app.post(
    "/v1/calculations",
    response_model=InventoryCalculationResult,
    summary="Calculate an auditable Scope 1 and Scope 2 inventory",
)
def create_calculation(
    request: InventoryCalculationRequest,
) -> InventoryCalculationResult:
    return calculate_inventory(request)
