"""Private object storage and malware-scanned evidence handling."""
from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
import zipfile
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import quote

import boto3
import clamd
from botocore.config import Config
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ActivityRecord, AuditEvent, Evidence

MAX_EVIDENCE_BYTES = 15 * 1024 * 1024
DOWNLOAD_URL_TTL_SECONDS = 300


def _safe_filename(filename: str | None) -> str:
    raw = (filename or "evidence").replace("\\", "/")
    name = PurePosixPath(raw).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    if not name:
        name = "evidence"
    return name[:180]


def detect_evidence_type(filename: str, content: bytes) -> tuple[str, str]:
    """Validate extension against file signature; reject ambiguous or active formats."""
    extension = PurePosixPath(filename).suffix.lower()
    if extension == ".pdf" and content.startswith(b"%PDF-"):
        return "application/pdf", extension
    if extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", extension
    if extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", extension
    if extension == ".csv":
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="CSV must be valid UTF-8 text") from None
        if not decoded.strip() or "\x00" in decoded:
            raise HTTPException(status_code=415, detail="CSV content is empty or invalid")
        return "text/csv", extension
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
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", extension
    raise HTTPException(
        status_code=415,
        detail="Only signature-verified PDF, PNG, JPEG, CSV and XLSX files are accepted",
    )


def scan_with_clamav(content: bytes) -> tuple[str, str | None]:
    """Fail closed if ClamAV is unavailable or returns an indeterminate result."""
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
        raise RuntimeError("ClamAV returned an unknown scan status")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Malware scanning is unavailable; upload was rejected") from None


@lru_cache(maxsize=1)
def _s3_client():
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    region = os.getenv("S3_REGION", "").strip()
    access_key = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    if not all((endpoint, region, access_key, secret_key)):
        raise HTTPException(status_code=503, detail="Private evidence storage is not configured")
    if os.getenv("ENVIRONMENT", "development").strip().lower() == "production" and not endpoint.startswith("https://"):
        raise HTTPException(status_code=503, detail="Production evidence storage endpoint must use HTTPS")
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


def upload_evidence(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str | None,
    content: bytes,
    activity_id: uuid.UUID | None = None,
    request_id: str | None = None,
    storage_client=None,
    scanner=None,
) -> Evidence:
    """Scan, upload privately, and persist immutable evidence metadata + audit."""
    if not content:
        raise HTTPException(status_code=400, detail="Evidence file is empty")
    if len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=413, detail="Evidence file exceeds the 15 MB limit")

    safe_name = _safe_filename(filename)
    media_type, _ = detect_evidence_type(safe_name, content)
    sha256 = hashlib.sha256(content).hexdigest()

    if activity_id is not None:
        activity = db.scalar(select(ActivityRecord).where(
            ActivityRecord.id == activity_id,
            ActivityRecord.tenant_id == tenant_id,
        ))
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity record not found")

    if scanner is None:
        scan_status, scan_detail = scan_with_clamav(content)
    else:
        result = scanner.instream(io.BytesIO(content))
        scan_status_raw, scan_detail = result.get("stream", (None, None))
        if scan_status_raw == "OK":
            scan_status = "clean"
        elif scan_status_raw == "FOUND":
            scan_status = "infected"
        else:
            raise HTTPException(status_code=503, detail="Malware scanner returned an unknown result")

    evidence_id = uuid.uuid4()
    if scan_status != "clean":
        db.add(AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="evidence.upload_rejected_malware",
            entity_type="evidence_upload_attempt",
            entity_id=str(evidence_id),
            after_state={
                "filename": safe_name,
                "sha256": sha256,
                "size_bytes": len(content),
                "scan_status": scan_status,
                "scan_detail": str(scan_detail or "Malware detected")[:300],
            },
            request_id=request_id,
        ))
        db.commit()
        raise HTTPException(status_code=422, detail="Malware detected; evidence was rejected")

    client = storage_client or _s3_client()
    bucket = _bucket_name()
    storage_key = f"tenant/{tenant_id}/evidence/{evidence_id}"
    put_args = {
        "Bucket": bucket,
        "Key": storage_key,
        "Body": content,
        "ContentLength": len(content),
        "ContentType": media_type,
        "ContentDisposition": f'attachment; filename="{safe_name}"',
        "CacheControl": "private, no-store",
        "Metadata": {
            "sha256": sha256,
            "tenant-id": str(tenant_id),
            "evidence-id": str(evidence_id),
        },
        "Tagging": f"tenant_id={tenant_id}&evidence_id={evidence_id}",
    }
    encryption = os.getenv("S3_SERVER_SIDE_ENCRYPTION", "AES256").strip()
    if encryption:
        put_args["ServerSideEncryption"] = encryption
        kms_key = os.getenv("S3_KMS_KEY_ID", "").strip()
        if encryption == "aws:kms" and kms_key:
            put_args["SSEKMSKeyId"] = kms_key

    try:
        client.put_object(**put_args)
    except Exception:
        raise HTTPException(status_code=503, detail="Private evidence storage upload failed") from None

    evidence = Evidence(
        id=evidence_id,
        tenant_id=tenant_id,
        activity_id=activity_id,
        uploaded_by=user_id,
        storage_key=storage_key,
        original_filename=safe_name,
        media_type=media_type,
        size_bytes=len(content),
        sha256=sha256,
        scan_status="clean",
    )
    db.add(evidence)
    db.add(AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="evidence.uploaded",
        entity_type="evidence",
        entity_id=str(evidence_id),
        after_state={
            "activity_id": str(activity_id) if activity_id else None,
            "filename": safe_name,
            "media_type": media_type,
            "size_bytes": len(content),
            "sha256": sha256,
            "scan_status": "clean",
            "storage_key": storage_key,
        },
        request_id=request_id,
    ))
    try:
        db.commit()
        db.refresh(evidence)
    except Exception:
        db.rollback()
        try:
            client.delete_object(Bucket=bucket, Key=storage_key)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Evidence metadata could not be committed") from None
    return evidence


def create_evidence_download_url(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    evidence: Evidence,
    request_id: str | None = None,
    storage_client=None,
) -> str:
    """Issue a short-lived signed URL only for clean evidence in the current tenant."""
    if evidence.scan_status != "clean":
        raise HTTPException(status_code=409, detail="Evidence is not cleared for download")
    client = storage_client or _s3_client()
    filename = quote(evidence.original_filename, safe="")
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": _bucket_name(),
                "Key": evidence.storage_key,
                "ResponseContentType": evidence.media_type,
                "ResponseContentDisposition": f"attachment; filename*=UTF-8''{filename}",
                "ResponseCacheControl": "private, no-store",
            },
            ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not create a private evidence download URL") from None

    db.add(AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="evidence.download_url.issued",
        entity_type="evidence",
        entity_id=str(evidence.id),
        after_state={
            "sha256": evidence.sha256,
            "expires_in_seconds": DOWNLOAD_URL_TTL_SECONDS,
        },
        request_id=request_id,
    ))
    db.commit()
    return url


def check_evidence_dependencies() -> None:
    """Readiness probe for private object storage and malware scanner."""
    try:
        _s3_client().head_bucket(Bucket=_bucket_name())
        host = os.getenv("CLAMAV_HOST", "").strip()
        if not host:
            raise RuntimeError("CLAMAV_HOST is not configured")
        scanner = clamd.ClamdNetworkSocket(
            host=host,
            port=int(os.getenv("CLAMAV_PORT", "3310")),
            timeout=5,
        )
        if scanner.ping() != "PONG":
            raise RuntimeError("ClamAV is not ready")
    except Exception:
        raise HTTPException(status_code=503, detail="Evidence storage or malware scanner is not ready") from None

