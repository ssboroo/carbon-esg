from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .calculator import calculate_inventory
from .schemas import InventoryCalculationRequest, InventoryCalculationResult

app = FastAPI(
    title="Carbon ESG API",
    version="0.2.0",
    description="API for auditable organizational greenhouse-gas accounting.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "carbon-esg-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Carbon ESG API",
        "version": "0.2.0",
        "docs": "/docs",
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
