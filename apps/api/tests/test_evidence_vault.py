"""Evidence Vault validation, malware rejection and private-storage integration tests."""
import io
import os
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.evidence_vault import (
    create_evidence_download_url,
    detect_evidence_type,
    upload_evidence,
)
from app.models import ActivityRecord, AuditEvent, EmissionFactor, Evidence, Tenant, User

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not MIGRATION_DATABASE_URL,
    reason="Runtime and migration PostgreSQL URLs are required",
)


class CleanScanner:
    def instream(self, stream):
        return {"stream": ("OK", None)}


class InfectedScanner:
    def instream(self, stream):
        return {"stream": ("FOUND", "Eicar-Test-Signature")}


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.download_params = None

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs

    def delete_object(self, **kwargs):
        self.objects.pop(kwargs["Key"], None)

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.download_params = (operation, Params, ExpiresIn)
        return "https://private-storage.example/signed-download"


def test_signature_validation_accepts_supported_formats_and_rejects_mismatch():
    assert detect_evidence_type("report.pdf", b"%PDF-1.7 sample")[0] == "application/pdf"
    assert detect_evidence_type("photo.png", b"\x89PNG\r\n\x1a\nrest")[0] == "image/png"
    assert detect_evidence_type("photo.jpg", b"\xff\xd8\xffrest")[0] == "image/jpeg"
    assert detect_evidence_type("data.csv", b"col1,col2\n1,2\n")[0] == "text/csv"

    workbook = io.BytesIO()
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    assert detect_evidence_type("data.xlsx", workbook.getvalue())[0].endswith("spreadsheetml.sheet")

    with pytest.raises(HTTPException) as invalid:
        detect_evidence_type("report.pdf", b"<html>not a PDF</html>")
    assert invalid.value.status_code == 415


def test_private_evidence_upload_is_scanned_audited_and_downloaded_with_short_url(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "private-evidence-test")
    seed_engine = create_engine(MIGRATION_DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id, factor_id, activity_id = uuid4(), uuid4(), uuid4(), uuid4()
    storage = FakeStorage()
    pdf = b"%PDF-1.7\nprivate test evidence\n"
    try:
        with Session(seed_engine) as seed:
            with seed.begin():
                seed.add(Tenant(
                    id=tenant_id,
                    legal_name="Evidence Vault Test Tenant",
                    country_code="MN",
                ))
                seed.add(User(
                    id=user_id,
                    email=f"{user_id}@evidence-test.invalid",
                    display_name="Evidence Test User",
                    is_active=True,
                ))
                seed.flush()
                seed.add(EmissionFactor(
                    id=factor_id,
                    tenant_id=tenant_id,
                    code="EVIDENCE-FACTOR-2026",
                    name="Evidence test factor",
                    value_kgco2e=Decimal("1.0"),
                    numerator_unit="kgCO2e",
                    denominator_unit="litre",
                    geography="MN",
                    source_name="Evidence test source",
                    source_url="https://example.org/evidence-factor",
                    source_year=2026,
                    version="v1",
                    methodology="scope1_activity_factor",
                    activity_category="mobile_combustion",
                    valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    approval_status="pending",
                ))
                seed.flush()
                seed.add(ActivityRecord(
                    id=activity_id,
                    tenant_id=tenant_id,
                    created_by=user_id,
                    name="Diesel activity",
                    scope="scope_1",
                    category="mobile_combustion",
                    amount=Decimal("10"),
                    unit="litre",
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                    factor_id=factor_id,
                    data_quality="unreviewed",
                ))

        with Session(engine) as db:
            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            evidence = upload_evidence(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                filename="../../fleet-proof.pdf",
                content=pdf,
                activity_id=activity_id,
                request_id="evidence-upload-test",
                storage_client=storage,
                scanner=CleanScanner(),
            )
            assert evidence.scan_status == "clean"
            assert evidence.original_filename == "fleet-proof.pdf"
            assert evidence.media_type == "application/pdf"
            assert evidence.size_bytes == len(pdf)
            assert len(evidence.sha256) == 64
            assert evidence.storage_key in storage.objects

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            with pytest.raises(DBAPIError):
                with seed_engine.begin() as owner:
                    owner.execute(
                        text("UPDATE evidence SET original_filename = 'tampered.pdf' WHERE id = :id"),
                        {"id": evidence.id},
                    )
            with pytest.raises(DBAPIError):
                with seed_engine.begin() as owner:
                    owner.execute(
                        text("DELETE FROM evidence WHERE id = :id"),
                        {"id": evidence.id},
                    )

            url = create_evidence_download_url(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                evidence=evidence,
                request_id="evidence-download-test",
                storage_client=storage,
            )
            assert url.startswith("https://")
            assert storage.download_params[0] == "get_object"
            assert storage.download_params[2] == 300

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            saved = db.scalar(select(Evidence).where(Evidence.id == evidence.id))
            events = db.scalars(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id
            )).all()
            assert saved is not None
            assert any(event.action == "evidence.uploaded" for event in events)
            assert any(event.action == "evidence.download_url.issued" for event in events)

            stored_before = len(storage.objects)
            with pytest.raises(HTTPException) as infected:
                upload_evidence(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    filename="infected.pdf",
                    content=pdf,
                    scanner=InfectedScanner(),
                    storage_client=storage,
                )
            assert infected.value.status_code == 422
            assert len(storage.objects) == stored_before
            db.rollback()

            db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            rejected = db.scalar(select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "evidence.upload_rejected_malware",
            ))
            assert rejected is not None
    finally:
        engine.dispose()
        seed_engine.dispose()


def test_upload_fails_closed_when_scanner_is_not_configured(monkeypatch):
    monkeypatch.delenv("CLAMAV_HOST", raising=False)
    with pytest.raises(HTTPException) as unavailable:
        upload_evidence(
            None,
            tenant_id=uuid4(),
            user_id=uuid4(),
            filename="report.pdf",
            content=b"%PDF-1.7 sample",
            storage_client=FakeStorage(),
        )
    assert unavailable.value.status_code == 503
