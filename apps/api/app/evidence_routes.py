"""Tenant-scoped Evidence Vault API."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import get_current_user
from .dependencies import get_db_session
from .evidence_vault import (
    DOWNLOAD_URL_TTL_SECONDS,
    MAX_EVIDENCE_BYTES,
    create_evidence_download_url,
    list_evidence,
    upload_evidence,
)
from .models import Evidence

router = APIRouter(
    prefix="/v1/organizations/{organization_id}/evidence",
    tags=["evidence"],
)


class EvidenceResponse(BaseModel):
    id: UUID
    activity_id: UUID | None
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    scan_status: str
    created_at: datetime


class EvidenceDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int


def _response(evidence: Evidence) -> EvidenceResponse:
    return EvidenceResponse(
        id=evidence.id,
        activity_id=evidence.activity_id,
        original_filename=evidence.original_filename,
        media_type=evidence.media_type,
        size_bytes=evidence.size_bytes,
        sha256=evidence.sha256,
        scan_status=evidence.scan_status,
        created_at=evidence.created_at,
    )


@router.post("", response_model=EvidenceResponse, status_code=201)
def upload_evidence_file(
    organization_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    activity_id: UUID | None = Form(default=None),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_EVIDENCE_BYTES + 1024 * 1024:
                raise HTTPException(status_code=413, detail="Multipart request exceeds the 16 MB limit")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from None
    content = file.file.read(MAX_EVIDENCE_BYTES + 1)
    return _response(
        upload_evidence(
            db,
            organization_id=organization_id,
            user_subject=user["sub"],
            filename=file.filename,
            content=content,
            activity_id=activity_id,
        )
    )


@router.get("", response_model=list[EvidenceResponse])
def get_evidence_list(
    organization_id: UUID,
    activity_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    records = list_evidence(
        db,
        organization_id=organization_id,
        user_subject=user["sub"],
        activity_id=activity_id,
        limit=limit,
        offset=offset,
    )
    return [_response(item) for item in records]


@router.get("/{evidence_id}/download", response_model=EvidenceDownloadResponse)
def download_evidence(
    organization_id: UUID,
    evidence_id: UUID,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    url = create_evidence_download_url(
        db,
        organization_id=organization_id,
        user_subject=user["sub"],
        evidence_id=evidence_id,
    )
    return {"download_url": url, "expires_in_seconds": DOWNLOAD_URL_TTL_SECONDS}
