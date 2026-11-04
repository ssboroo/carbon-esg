from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db
from .models import LegalAct, Standard

router = APIRouter(prefix="/v1", tags=["legal-registry"])

@router.get("/legal/acts")
def list_legal_acts(db: Session = Depends(get_db)):
    rows = db.scalars(select(LegalAct).where(LegalAct.jurisdiction == "MN").order_by(LegalAct.title_mn)).all()
    return [{"id": str(x.id), "code": x.official_identifier, "title": x.title_mn, "status": x.legal_status, "source_url": x.official_source_url} for x in rows]

@router.get("/standards")
def list_standards(db: Session = Depends(get_db)):
    rows = db.scalars(select(Standard).order_by(Standard.standard_code)).all()
    return [{"id": str(x.id), "code": x.standard_code, "title": x.title_mn, "status": x.status, "source_url": x.official_catalog_url} for x in rows]

from uuid import UUID
from fastapi import HTTPException
from app.models import LegalActVersion, LegalProvision


@router.get("/legal/acts/{act_id}/text")
def latest_legal_text(act_id: UUID, db: Session = Depends(get_db)):
    act = db.get(LegalAct, act_id)
    if act is None or act.jurisdiction != "MN":
        raise HTTPException(status_code=404, detail="Legal act not found")
    version = db.scalar(select(LegalActVersion).where(
        LegalActVersion.legal_act_id == act.id
    ).order_by(LegalActVersion.retrieved_at.desc()))
    if version is None:
        raise HTTPException(status_code=404, detail="Full text has not been imported")
    rows = db.scalars(select(LegalProvision).where(
        LegalProvision.legal_act_version_id == version.id
    ).order_by(LegalProvision.provision_code)).all()
    return {
        "title": act.title_mn,
        "version": version.version_label,
        "sha256": version.content_sha256,
        "source_url": version.source_url,
        "full_text": version.full_text,
        "provisions": [{"code": row.provision_code, "heading": row.heading,
                        "parent_id": str(row.parent_provision_id) if row.parent_provision_id else None,
                        "text": row.full_text} for row in rows],
    }
