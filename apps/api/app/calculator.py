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
    """Deterministic CO2e calculation with distinct Scope 2 accounting bases."""
    results: list[RecordCalculationResult] = []
    scope_1_kg = Decimal("0")
    scope_2_location_kg = Decimal("0")
    scope_2_market_kg = Decimal("0")
    scope_2_unclassified_kg = Decimal("0")

    for record in request.records:
        emissions_kg = record.activity_amount * record.emission_factor_kgco2e_per_unit
        if record.scope == "scope_1":
            scope_1_kg += emissions_kg
        elif record.scope_2_basis == "location_based":
            scope_2_location_kg += emissions_kg
        elif record.scope_2_basis == "market_based":
            scope_2_market_kg += emissions_kg
        else:
            scope_2_unclassified_kg += emissions_kg

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
                scope_2_basis=record.scope_2_basis,
            )
        )

    # Location-based is the primary Scope 2 figure when both methods are present.
    # Market-based is always exposed separately; the two are never added together.
    selected_scope_2_kg = (
        scope_2_location_kg
        if scope_2_location_kg > 0
        else scope_2_market_kg
        if scope_2_market_kg > 0
        else scope_2_unclassified_kg
    )
    scope_1_tonnes = scope_1_kg / KG_PER_TONNE
    location_tonnes = scope_2_location_kg / KG_PER_TONNE
    market_tonnes = scope_2_market_kg / KG_PER_TONNE
    selected_scope_2_tonnes = selected_scope_2_kg / KG_PER_TONNE

    return InventoryCalculationResult(
        reporting_period_start=request.reporting_period_start,
        reporting_period_end=request.reporting_period_end,
        scope_1_tco2e=round_emissions(scope_1_tonnes),
        scope_2_tco2e=round_emissions(selected_scope_2_tonnes),
        scope_2_location_based_tco2e=round_emissions(location_tonnes),
        scope_2_market_based_tco2e=round_emissions(market_tonnes),
        total_location_based_tco2e=round_emissions(scope_1_tonnes + location_tonnes),
        total_market_based_tco2e=round_emissions(scope_1_tonnes + market_tonnes),
        total_tco2e=round_emissions(scope_1_tonnes + selected_scope_2_tonnes),
        records=results,
    )
