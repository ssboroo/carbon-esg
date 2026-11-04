from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


Scope = Literal["scope_1", "scope_2"]

SCOPE_1_CATEGORIES = {
    "stationary_combustion",
    "mobile_combustion",
    "process",
    "fugitive",
}
SCOPE_2_CATEGORIES = {
    "purchased_electricity",
    "purchased_heat",
    "purchased_steam",
    "purchased_cooling",
}


class ActivityInput(BaseModel):
    """One activity record paired with an explicitly supplied emission factor."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    scope: Scope
    category: str = Field(min_length=1, max_length=64)
    activity_amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    activity_unit: str = Field(min_length=1, max_length=32)
    emission_factor_kgco2e_per_unit: Decimal = Field(
        ge=0, max_digits=20, decimal_places=12
    )
    factor_unit: str = Field(
        min_length=1,
        max_length=32,
        description="Must be the same denominator unit as activity_unit.",
    )
    factor_source_name: str = Field(min_length=2, max_length=200)
    factor_source_url: HttpUrl
    factor_year: int = Field(ge=1900, le=2200)
    factor_version: str = Field(min_length=1, max_length=80)
    scope_2_basis: Literal["location_based", "market_based"] | None = None

    @field_validator("factor_source_url")
    @classmethod
    def source_must_use_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Emission-factor source URL must use HTTPS")
        return value

    @model_validator(mode="after")
    def validate_scope_category_and_units(self):
        if self.activity_unit.strip().lower() != self.factor_unit.strip().lower():
            raise ValueError("activity_unit must match the emission-factor denominator unit")

        allowed = SCOPE_1_CATEGORIES if self.scope == "scope_1" else SCOPE_2_CATEGORIES
        if self.category not in allowed:
            raise ValueError(
                f"Category '{self.category}' is not valid for {self.scope}"
            )
        if self.scope == "scope_1" and self.scope_2_basis is not None:
            raise ValueError("scope_2_basis is only valid for Scope 2 records")
        return self



class ApprovedActivityInput(BaseModel):
    """Activity data referencing an already approved tenant factor."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    scope: Scope
    category: str = Field(min_length=1, max_length=64)
    activity_amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    activity_unit: str = Field(min_length=1, max_length=32)
    factor_id: UUID
    scope_2_basis: Literal["location_based", "market_based"] | None = None

    @model_validator(mode="after")
    def validate_scope_category_and_basis(self):
        allowed = SCOPE_1_CATEGORIES if self.scope == "scope_1" else SCOPE_2_CATEGORIES
        if self.category not in allowed:
            raise ValueError(f"Category '{self.category}' is not valid for {self.scope}")
        if self.scope == "scope_1" and self.scope_2_basis is not None:
            raise ValueError("scope_2_basis is only valid for Scope 2 records")
        if self.scope == "scope_2" and self.scope_2_basis is None:
            raise ValueError("Scope 2 records must declare location_based or market_based")
        return self


class ApprovedInventoryCalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reporting_period_start: date
    reporting_period_end: date
    records: list[ApprovedActivityInput] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_reporting_period(self):
        if self.reporting_period_end < self.reporting_period_start:
            raise ValueError("reporting_period_end must be on or after reporting_period_start")
        return self

class InventoryCalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reporting_period_start: date
    reporting_period_end: date
    records: list[ActivityInput] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_reporting_period(self):
        if self.reporting_period_end < self.reporting_period_start:
            raise ValueError("reporting_period_end must be on or after reporting_period_start")
        scope2_basis_values = {record.scope_2_basis for record in self.records if record.scope == "scope_2"}
        if None in scope2_basis_values and len(scope2_basis_values) > 1:
            raise ValueError("Do not mix Scope 2 records with and without an accounting basis")
        return self


class RecordCalculationResult(BaseModel):
    name: str
    scope: Scope
    category: str
    activity_amount: Decimal
    activity_unit: str
    emission_factor_kgco2e_per_unit: Decimal
    emissions_kgco2e: Decimal
    emissions_tco2e: Decimal
    factor_source_name: str
    factor_source_url: str
    factor_year: int
    factor_version: str
    scope_2_basis: Literal["location_based", "market_based"] | None = None


class InventoryCalculationResult(BaseModel):
    reporting_period_start: date
    reporting_period_end: date
    scope_1_tco2e: Decimal
    scope_2_tco2e: Decimal
    scope_2_location_based_tco2e: Decimal = Decimal("0")
    scope_2_market_based_tco2e: Decimal = Decimal("0")
    total_location_based_tco2e: Decimal = Decimal("0")
    total_market_based_tco2e: Decimal = Decimal("0")
    total_tco2e: Decimal
    records: list[RecordCalculationResult]
    methodology: str = "activity_data × emission_factor_kgCO2e_per_unit; kgCO2e / 1000 = tCO2e"
    snapshot_id: UUID | None = None
    review_status: Literal["preview", "pending_review"] = "preview"
    factor_status: Literal["unverified", "approved"] = "unverified"
