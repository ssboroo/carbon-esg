"""Tenant-scoped Evidence Vault API."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import TenantContext, require_roles
from .database import get_db
from .evidence_vault import (
    DOWNLOAD_URL_TTL_SECONDS,
    MAX_EVIDENCE_BYTES,
    create_evidence_download_url,
    upload_evidence,
)
from .models import Evidence

router = APIRouter(prefix="/v1/evidence", tags=["evidence"])


class EvidenceResponse(BaseModel):
    id: UUID
    activity_id: UUID | None
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    scan_status: str
    created_at: str


class EvidenceDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int


def _response(evidence: Evidence) -> dict:
    return {
        "id": evidence.id,
        "activity_id": evidence.activity_id,
        "original_filename": evidence.original_filename,
        "media_type": evidence.media_type,
        "size_bytes": evidence.size_bytes,
        "sha256": evidence.sha256,
        "scan_status": evidence.scan_status,
        "created_at": evidence.created_at.isoformat(),
    }


@router.post("", response_model=EvidenceResponse, status_code=201)
def upload_evidence_file(
    request: Request,
    file: UploadFile = File(...),
    activity_id: UUID | None = Form(default=None),
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    """Upload private evidence after file-signature validation and ClamAV scan."""
    content = file.file.read(MAX_EVIDENCE_BYTES + 1)
    request_id = request.headers.get("X-Request-ID")
    if request_id and len(request_id) > 80:
        request_id = None
    evidence = upload_evidence(
        db,
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
        filename=file.filename,
        content=content,
        activity_id=activity_id,
        request_id=request_id,
    )
    return _response(evidence)


@router.get("", response_model=list[EvidenceResponse])
def list_evidence(
    activity_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager", "reviewer", "viewer")),
    db: Session = Depends(get_db),
):
    query = select(Evidence).where(Evidence.tenant_id == tenant.tenant_id)
    if activity_id is not None:
        query = query.where(Evidence.activity_id == activity_id)
    records = db.scalars(
        query.order_by(Evidence.created_at.desc(), Evidence.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_response(item) for item in records]


@router.get("/{evidence_id}/download", response_model=EvidenceDownloadResponse)
def get_evidence_download_url(
    evidence_id: UUID,
    request: Request,
    tenant: TenantContext = Depends(require_roles("owner", "admin", "manager", "reviewer", "viewer")),
    db: Session = Depends(get_db),
):
    evidence = db.scalar(select(Evidence).where(
        Evidence.id == evidence_id,
        Evidence.tenant_id == tenant.tenant_id,
    ))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    request_id = request.headers.get("X-Request-ID")
    if request_id and len(request_id) > 80:
        request_id = None
    url = create_evidence_download_url(
        db,
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
        evidence=evidence,
        request_id=request_id,
    )
    return {
        "download_url": url,
        "expires_in_seconds": DOWNLOAD_URL_TTL_SECONDS,
    }
