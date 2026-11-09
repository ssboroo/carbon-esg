import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .schemas import SCOPE_1_CATEGORIES, SCOPE_2_CATEGORIES, Scope


class EmissionFactorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
    name: str = Field(min_length=2, max_length=200)
    scope: Scope
    scope_2_method: Literal["location_based", "market_based"] | None = None
    category: str = Field(min_length=1, max_length=64)
    factor_value: Decimal = Field(ge=0, max_digits=24, decimal_places=12)
    factor_unit: str = Field(min_length=1, max_length=32)
    gas_basis: Literal["CO2e"] = "CO2e"
    source_name: str = Field(min_length=2, max_length=200)
    source_url: HttpUrl
    source_document: str | None = Field(default=None, max_length=255)
    factor_year: int = Field(ge=1900, le=2200)
    version: str = Field(min_length=1, max_length=80)
    geography_code: str = Field(min_length=1, max_length=32)
    geography_name: str = Field(min_length=2, max_length=160)
    geography_boundary: Literal["global", "national", "subnational", "grid", "market", "facility", "other"]
    valid_from: date
    valid_to: date

    @field_validator("factor_code", "name", "factor_unit", "source_name", "version")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
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

    @field_validator("geography_name")
    @classmethod
    def trim_geography_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Geography name must contain at least 2 characters")
        return value

    @field_validator("source_document")
    @classmethod
    def trim_source_document(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https" or not value.host:
            raise ValueError("Emission-factor source URL must use HTTPS")
        return value

    @model_validator(mode="after")
    def validate_scope_category(self):
        allowed = SCOPE_1_CATEGORIES if self.scope == "scope_1" else SCOPE_2_CATEGORIES
        if self.category not in allowed:
            raise ValueError("Category does not belong to the selected GHG scope")
        if self.scope == "scope_1" and self.scope_2_method is not None:
            raise ValueError("Scope 1 factors must not specify a Scope 2 method")
        if self.scope == "scope_2" and self.scope_2_method is None:
            raise ValueError("Scope 2 factors require a location-based or market-based method")
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        if self.geography_code == "GLOBAL" and self.geography_boundary != "global":
            raise ValueError("GLOBAL geography code requires the global boundary")
        if self.geography_boundary == "global" and self.geography_code != "GLOBAL":
            raise ValueError("Global boundary must use the GLOBAL geography code")
        return self


class FactorReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=10, max_length=2000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Review note must contain at least 10 non-whitespace characters")
        return value


class FactorReviewQueueItem(BaseModel):
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
    approval_status: Literal["pending", "approved", "rejected"]
    submitted_by_subject: str | None
    reviewer_subject: str | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
