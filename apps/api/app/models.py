"""Tenant-scoped persistence schema for auditable GHG inventories.

Authentication is intentionally not implemented here. API routes must obtain
organization_id from a verified identity/membership layer before querying data.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_subject", name="uq_membership_org_subject"),
        CheckConstraint("role IN ('owner', 'admin', 'editor', 'viewer')", name="ck_membership_role"),
        Index("ix_memberships_subject", "user_subject"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # Opaque subject from the future verified identity provider; never an email/password.
    user_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmissionFactor(Base):
    __tablename__ = "emission_factors"
    __table_args__ = (
        UniqueConstraint("organization_id", "factor_code", "version", name="uq_factor_org_code_version"),
        UniqueConstraint("organization_id", "id", name="uq_factor_org_id"),
        CheckConstraint("factor_value >= 0", name="ck_factor_nonnegative"),
        CheckConstraint("factor_year BETWEEN 1900 AND 2200", name="ck_factor_year"),
        CheckConstraint("source_url LIKE 'https://%'", name="ck_factor_https_source"),
        CheckConstraint("scope IN ('scope_1', 'scope_2')", name="ck_factor_scope"),
        Index("ix_factors_org_scope_category", "organization_id", "scope", "category"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    factor_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_value: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    factor_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    gas_basis: Mapped[str] = mapped_column(String(24), nullable=False, default="CO2e")
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[str | None] = mapped_column(String(255))
    factor_year: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_by_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmissionFactorReview(Base):
    """One immutable human decision for an immutable emission-factor version."""
    __tablename__ = "emission_factor_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "emission_factor_id"],
            ["emission_factors.organization_id", "emission_factors.id"],
            ondelete="RESTRICT",
            name="fk_factor_review_factor_tenant",
        ),
        UniqueConstraint("organization_id", "emission_factor_id", name="uq_factor_review_org_factor"),
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_factor_review_decision"),
        CheckConstraint("length(btrim(review_note)) >= 10", name="ck_factor_review_note"),
        Index("ix_factor_reviews_org_decision", "organization_id", "decision", "reviewed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    emission_factor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    review_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Inventory(Base):
    __tablename__ = "inventories"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_inventory_org_id"),
        CheckConstraint("reporting_period_end >= reporting_period_start", name="ck_inventory_period"),
        CheckConstraint("status IN ('draft', 'review', 'approved')", name="ck_inventory_status"),
        Index("ix_inventories_org_period", "organization_id", "reporting_period_start", "reporting_period_end"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    reporting_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActivityRecord(Base):
    __tablename__ = "activity_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "inventory_id"],
            ["inventories.organization_id", "inventories.id"],
            ondelete="CASCADE",
            name="fk_activity_inventory_tenant",
        ),
        ForeignKeyConstraint(
            ["organization_id", "emission_factor_id"],
            ["emission_factors.organization_id", "emission_factors.id"],
            name="fk_activity_factor_tenant",
        ),
        CheckConstraint("activity_amount > 0", name="ck_activity_amount_positive"),
        CheckConstraint("factor_value_snapshot >= 0 AND emissions_kgco2e >= 0", name="ck_activity_emissions_nonnegative"),
        CheckConstraint("activity_unit = factor_unit_snapshot", name="ck_activity_units_match"),
        CheckConstraint("scope IN ('scope_1', 'scope_2')", name="ck_activity_scope"),
        Index("ix_activity_org_inventory", "organization_id", "inventory_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    inventory_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    emission_factor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_amount: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    # Factor and emissions are snapshotted so later factor additions cannot alter past reports.
    factor_value_snapshot: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    factor_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    emissions_kgco2e: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CalculationRun(Base):
    __tablename__ = "calculation_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "inventory_id"],
            ["inventories.organization_id", "inventories.id"],
            ondelete="CASCADE",
            name="fk_calculation_inventory_tenant",
        ),
        Index("ix_calculation_org_inventory_created", "organization_id", "inventory_id", "created_at"),
        CheckConstraint("scope_1_kgco2e >= 0 AND scope_2_kgco2e >= 0", name="ck_calculation_scopes_nonnegative"),
        CheckConstraint("total_kgco2e = scope_1_kgco2e + scope_2_kgco2e", name="ck_calculation_total_matches_scopes"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    inventory_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    scope_1_kgco2e: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    scope_2_kgco2e: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    total_kgco2e: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Evidence(Base):
    """Immutable metadata for malware-scanned files stored in private object storage."""
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_evidence_storage_key"),
        UniqueConstraint("organization_id", "id", name="uq_evidence_org_id"),
        CheckConstraint("size_bytes BETWEEN 1 AND 15728640", name="ck_evidence_size"),
        CheckConstraint("scan_status = 'clean'", name="ck_evidence_clean_only"),
        Index("ix_evidence_org_created", "organization_id", "created_at"),
        Index("ix_evidence_org_activity", "organization_id", "activity_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("activity_records.id", ondelete="SET NULL"))
    uploaded_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(180), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_org_entity", "organization_id", "entity_type", "entity_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
