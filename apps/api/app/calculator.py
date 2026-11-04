from decimal import Decimal, ROUND_HALF_UP

from .schemas import (
    InventoryCalculationRequest,
    InventoryCalculationResult,
    RecordCalculationResult,
)

SIX_PLACES = Decimal("0.000001")
KG_PER_TONNE = Decimal("1000")


def round_emissions(value: Decimal) -> Decimal:
    return value.quantize(SIX_PLACES, rounding=ROUND_HALF_UP)


def calculate_inventory(
    request: InventoryCalculationRequest,
) -> InventoryCalculationResult:
    """Calculate CO2e using only the factor explicitly supplied with each record.

    The factor is assumed to already be expressed as kgCO2e per activity unit.
    No default factor lookup or AI-generated factor is performed here.
    """
    results: list[RecordCalculationResult] = []
    scope_1_kg = Decimal("0")
    scope_2_kg = Decimal("0")

    for record in request.records:
        emissions_kg = record.activity_amount * record.emission_factor_kgco2e_per_unit
        if record.scope == "scope_1":
            scope_1_kg += emissions_kg
        else:
            scope_2_kg += emissions_kg

        results.append(
            RecordCalculationResult(
                name=record.name,
                scope=record.scope,
                category=record.category,
                activity_amount=record.activity_amount,
                activity_unit=record.activity_unit,
                emission_factor_kgco2e_per_unit=record.emission_factor_kgco2e_per_unit,
                emissions_kgco2e=round_emissions(emissions_kg),
                emissions_tco2e=round_emissions(emissions_kg / KG_PER_TONNE),
                factor_source_name=record.factor_source_name,
                factor_source_url=str(record.factor_source_url),
                factor_year=record.factor_year,
                factor_version=record.factor_version,
            )
        )

    scope_1_tonnes = scope_1_kg / KG_PER_TONNE
    scope_2_tonnes = scope_2_kg / KG_PER_TONNE
    total_tonnes = scope_1_tonnes + scope_2_tonnes

    return InventoryCalculationResult(
        reporting_period_start=request.reporting_period_start,
        reporting_period_end=request.reporting_period_end,
        scope_1_tco2e=round_emissions(scope_1_tonnes),
        scope_2_tco2e=round_emissions(scope_2_tonnes),
        total_tco2e=round_emissions(total_tonnes),
        records=results,
    )
