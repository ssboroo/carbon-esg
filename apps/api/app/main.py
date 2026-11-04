import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .calculator import calculate_inventory
from .schemas import InventoryCalculationRequest, InventoryCalculationResult

app = FastAPI(
    title="Carbon ESG API",
    version="0.3.0",
    description="API for auditable organizational greenhouse-gas accounting.",
    docs_url="/docs",
    redoc_url=None,
)

# Explicit allow-list. Never use "*" with credentialed browser requests.
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
if "*" in cors_origins:
    raise RuntimeError("CORS_ORIGINS must contain explicit trusted origins, not '*'.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "carbon-esg-api", "version": "0.3.0"}


@app.get("/", tags=["operations"])
def root() -> dict[str, str]:
    return {
        "name": "Carbon ESG API",
        "version": "0.3.0",
        "docs": "/docs",
    }


@app.post(
    "/v1/calculations",
    response_model=InventoryCalculationResult,
    summary="Calculate an auditable Scope 1 and Scope 2 inventory",
    tags=["calculations"],
)
def create_calculation(
    request: InventoryCalculationRequest,
) -> InventoryCalculationResult:
    return calculate_inventory(request)
