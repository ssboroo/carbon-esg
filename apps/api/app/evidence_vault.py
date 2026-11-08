"""Private object storage and malware-scanned evidence handling."""

from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import quote

import boto3
import clamd
from botocore.config import Config
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import set_identity_context, set_tenant_context
from .models import ActivityRecord, AuditEvent, Evidence, OrganizationMembership

MAX_EVIDENCE_BYTES = 15 * 1024 * 1024
DOWNLOAD_URL_TTL_SECONDS = 300
UPLOAD_ROLES = {"owner", "admin", "editor"}


def safe_filename(filename: str | None) -> str:
    raw = (filename or "evidence").replace("\\", "/")
    name = PurePosixPath(raw).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    name = name.replace('"', "_").replace("'", "_")
    return (name or "evidence")[:180]


def detect_evidence_type(filename: str, content: bytes) -> str:
    """Check extension and file signature; reject active/ambiguous formats."""
    extension = PurePosixPath(filename).suffix.lower()
    if extension == ".pdf" and content.startswith(b"%PDF-"):
        return "application/pdf"
    if extension in {".jpg", ".jpeg"} and content.startswith(b"\\xff\\xd8\\xff"):
        return "image/jpeg"
    if extension == ".png" and content.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        return "image/png"
    if extension == ".csv":
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="CSV must be valid UTF-8 text") from None
        if not decoded.strip() or "\\x00" in decoded:
            raise HTTPException(status_code=415, detail="CSV content is empty or invalid")
        return "text/csv"
    if extension == ".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
                total_size = sum(item.file_size for item in archive.infolist())
                if (
                    "[Content_Types].xml" not in names
                    or "xl/workbook.xml" not in names
                    or len(names) > 2000
                    or total_size > 50 * 1024 * 1024
                ):
                    raise HTTPException(status_code=415, detail="Invalid or oversized XLSX workbook")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=415, detail="Invalid XLSX archive") from None
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raise HTTPException(
        status_code=415,
        detail="Only signature-verified PDF, PNG, JPEG, CSV and XLSX files are accepted",
    )


def scan_with_clamav(content: bytes):
    """Fail closed if the malware scanner is missing or cannot give a clean result."""
    host = os.getenv("CLAMAV_HOST", "").strip()
    if not host:
        raise HTTPException(status_code=503, detail="Malware scanner is not configured")
    try:
        scanner = clamd.ClamdNetworkSocket(
            host=host,
            port=int(os.getenv("CLAMAV_PORT", "3310")),
            timeout=10,
        )
        if scanner.ping() != "PONG":
            raise RuntimeError("ClamAV did not respond to PING")
        result = scanner.instream(io.BytesIO(content))
        status, detail = result.get("stream", (None, None))
        if status == "OK":
            return "clean", None
        if status == "FOUND":
            return "infected", str(detail or "Malware detected")
        raise RuntimeError("ClamAV returned an unknown status")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Malware scanning unavailable; upload rejected") from None


@lru_cache(maxsize=1)
def _s3_client():
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    region = os.getenv("S3_REGION", "").strip()
    access_key = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    if not all((endpoint, region, access_key, secret_key)):
        raise HTTPException(status_code=503, detail="Private evidence storage is not configured")
    if os.getenv("ENVIRONMENT", "development").strip().lower() == "production" and not endpoint.startswith("https://"):
        raise HTTPException(status_code=503, detail="Production evidence storage must use HTTPS")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _bucket_name() -> str:
    bucket = os.getenv("S3_BUCKET", "").strip()
    if not bucket:
        raise HTTPException(status_code=503, detail="Evidence bucket is not configured")
    return bucket


def _membership_and_tenant(db: Session, organization_id: uuid.UUID, user_subject: str, *, write: bool) -> None:
    set_identity_context(db, user_subject)
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_subject == user_subject,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Байгууллага олдсонгүй эсвэл танд хандах эрх байхгүй")
    if write and membership.role not in UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail="Баримт байршуулахад owner, admin эсвэл editor эрх шаардлагатай")
    set_tenant_context(db, str(organization_id))


def upload_evidence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_subject: str,
    filename: str | None,
    content: bytes,
    activity_id: uuid.UUID | None = None,
    request_id: str | None = None,
    storage_client=None,
    scanner=None,
) -> Evidence:
    if not content:
        raise HTTPException(status_code=400, detail="Evidence file is empty")
    if len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=413, detail="Evidence file exceeds the 15 MB limit")

    safe_name = safe_filename(filename)
    media_type = detect_evidence_type(safe_name, content)
    digest = hashlib.sha256(content).hexdigest()
    client = storage_client or _s3_client()
    bucket = _bucket_name()
    evidence_id = uuid.uuid4()
    uploaded_key: str | None = None
    infected = False
    evidence: Evidence | None = None

    try:
        with db.begin():
            _membership_and_tenant(db, organization_id, user_subject, write=True)
            if activity_id is not None:
                activity = db.scalar(
                    select(ActivityRecord).where(
                        ActivityRecord.id == activity_id,
                        ActivityRecord.organization_id == organization_id,
                    )
                )
                if activity is None:
                    raise HTTPException(status_code=404, detail="Activity record not found")

            if scanner is None:
                scan_status, scan_detail = scan_with_clamav(content)
            else:
                result = scanner.instream(io.BytesIO(content))
                raw_status, scan_detail = result.get("stream", (None, None))
                if raw_status == "OK":
                    scan_status = "clean"
                elif raw_status == "FOUND":
                    scan_status = "infected"
                else:
                    raise HTTPException(status_code=503, detail="Malware scanner returned an unknown result")

            if scan_status != "clean":
                db.add(AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user_subject,
                    action="evidence.upload_rejected_malware",
                    entity_type="evidence_upload_attempt",
                    entity_id=str(evidence_id),
                    details={
                        "filename": safe_name,
                        "sha256": digest,
                        "size_bytes": len(content),
                        "scan_status": scan_status,
                        "scan_detail": str(scan_detail or "Malware detected")[:300],
                    },
                ))
                infected = True
            else:
                storage_key = f"organizations/{organization_id}/evidence/{evidence_id}"
                put_args = {
                    "Bucket": bucket,
                    "Key": storage_key,
                    "Body": content,
                    "ContentLength": len(content),
                    "ContentType": media_type,
                    "ContentDisposition": f'attachment; filename="{safe_name}"',
                    "CacheControl": "private, no-store",
                    "Metadata": {
                        "sha256": digest,
                        "organization-id": str(organization_id),
                        "evidence-id": str(evidence_id),
                    },
                }
                encryption = os.getenv("S3_SERVER_SIDE_ENCRYPTION", "AES256").strip()
                if encryption:
                    put_args["ServerSideEncryption"] = encryption
                    kms_key = os.getenv("S3_KMS_KEY_ID", "").strip()
                    if encryption == "aws:kms" and kms_key:
                        put_args["SSEKMSKeyId"] = kms_key
                client.put_object(**put_args)
                uploaded_key = storage_key

                evidence = Evidence(
                    id=evidence_id,
                    organization_id=organization_id,
                    activity_id=activity_id,
                    uploaded_by_subject=user_subject,
                    storage_key=storage_key,
                    original_filename=safe_name,
                    media_type=media_type,
                    size_bytes=len(content),
                    sha256=digest,
                    scan_status="clean",
                    created_at=datetime.now(timezone.utc),
                )
                db.add(evidence)
                db.add(AuditEvent(
                    organization_id=organization_id,
                    actor_subject=user_subject,
                    action="evidence.uploaded",
                    entity_type="evidence",
                    entity_id=str(evidence_id),
                    details={
                        "activity_id": str(activity_id) if activity_id else None,
                        "filename": safe_name,
                        "media_type": media_type,
                        "size_bytes": len(content),
                        "sha256": digest,
                        "scan_status": "clean",
                        "storage_key": storage_key,
                    },
                ))
    except Exception:
        if uploaded_key:
            try:
                client.delete_object(Bucket=bucket, Key=uploaded_key)
            except Exception:
                pass
        raise

    if infected:
        raise HTTPException(status_code=422, detail="Malware detected; evidence was rejected")
    assert evidence is not None
    return evidence


def list_evidence(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_subject: str,
    activity_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Evidence]:
    with db.begin():
        _membership_and_tenant(db, organization_id, user_subject, write=False)
        query = select(Evidence).where(Evidence.organization_id == organization_id)
        if activity_id is not None:
            query = query.where(Evidence.activity_id == activity_id)
        return db.scalars(
            query.order_by(Evidence.created_at.desc(), Evidence.id.desc()).limit(limit).offset(offset)
        ).all()


def create_evidence_download_url(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_subject: str,
    evidence_id: uuid.UUID,
    storage_client=None,
    request_id: str | None = None,
) -> str:
    client = storage_client or _s3_client()
    with db.begin():
        _membership_and_tenant(db, organization_id, user_subject, write=False)
        evidence = db.scalar(
            select(Evidence).where(
                Evidence.id == evidence_id,
                Evidence.organization_id == organization_id,
            )
        )
        if evidence is None:
            raise HTTPException(status_code=404, detail="Evidence not found")
        if evidence.scan_status != "clean":
            raise HTTPException(status_code=409, detail="Evidence is not cleared for download")
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": _bucket_name(),
                "Key": evidence.storage_key,
                "ResponseContentType": evidence.media_type,
                "ResponseContentDisposition": f"attachment; filename*=UTF-8''{quote(evidence.original_filename, safe='')}",
                "ResponseCacheControl": "private, no-store",
            },
            ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
        )
        db.add(AuditEvent(
            organization_id=organization_id,
            actor_subject=user_subject,
            action="evidence.download_url.issued",
            entity_type="evidence",
            entity_id=str(evidence.id),
            details={"sha256": evidence.sha256, "expires_in_seconds": DOWNLOAD_URL_TTL_SECONDS},
        ))
    return url
