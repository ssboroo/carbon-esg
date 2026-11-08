from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=3,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Organization name must contain at least 2 characters")
        return value


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str
