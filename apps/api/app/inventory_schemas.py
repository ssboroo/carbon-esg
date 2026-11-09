import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schemas import Scope


class InventoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    reporting_period_start: date
    reporting_period_end: date
    scope_2_primary_method: Literal["location_based", "market_based"] = "location_based"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Inventory name must contain at least 2 characters")
        return value

    @model_validator(mode="after")
    def validate_reporting_period(self):
        if self.reporting_period_end < self.reporting_period_start:
            raise ValueError("reporting_period_end must be on or after reporting_period_start")
        return self


class ActivityRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    scope: Scope
    category: str = Field(min_length=1, max_length=64)
    activity_amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    activity_unit: str = Field(min_length=1, max_length=32)
    geography_code: str = Field(min_length=1, max_length=32)
    geography_name: str = Field(min_length=2, max_length=160)
    emission_factor_id: UUID

    @field_validator("name", "activity_unit", "geography_name")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("geography_code")
    @classmethod
    def normalize_geography_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._:-]{0,31}", value):
            raise ValueError("Geography code must use 1-32 uppercase letters, digits, dot, underscore, colon or hyphen")
        return value


class InventorySummary(BaseModel):
    id: UUID
    name: str
    reporting_period_start: date
    reporting_period_end: date
    status: str
    scope_2_primary_method: Literal["location_based", "market_based"] = "location_based"


class EmissionFactorSummary(BaseModel):
    id: UUID
    factor_code: str
    name: str
    scope: Scope
    scope_2_method: Literal["location_based", "market_based"] | None
    category: str
    factor_value: Decimal
    factor_unit: str
    gas_basis: str
    source_name: str
    source_url: str
    source_document: str | None
    factor_year: int
    version: str
    geography_code: str
    geography_name: str
    geography_boundary: Literal["global", "national", "subnational", "grid", "market", "facility", "other"]
    valid_from: date | None
    valid_to: date | None
    approval_status: Literal["approved"] = "approved"


class ActivityRecordSummary(BaseModel):
    id: UUID
    name: str
    scope: Scope
    scope_2_method: Literal["location_based", "market_based"] | None
    category: str
    activity_geography_code: str
    activity_geography_name: str
    factor_geography_code: str
    factor_geography_name: str
    factor_geography_boundary: Literal["global", "national", "subnational", "grid", "market", "facility", "other"]
    factor_valid_from: date | None
    factor_valid_to: date | None
    activity_amount: Decimal
    activity_unit: str
    emission_factor_id: UUID
    factor_value_snapshot: Decimal
    factor_unit_snapshot: str
    factor_code: str
    factor_version: str
    factor_source_name: str
    factor_source_url: str
    factor_year: int
    emissions_kgco2e: Decimal


class CalculationRunSummary(BaseModel):
    id: UUID
    inventory_id: UUID
    scope_1_kgco2e: Decimal
    scope_2_kgco2e: Decimal
    scope_2_location_based_kgco2e: Decimal | None
    scope_2_market_based_kgco2e: Decimal | None
    total_location_based_kgco2e: Decimal | None
    total_market_based_kgco2e: Decimal | None
    scope_2_primary_method: Literal["location_based", "market_based"]
    total_kgco2e: Decimal
    methodology_version: str
    created_at: datetime
