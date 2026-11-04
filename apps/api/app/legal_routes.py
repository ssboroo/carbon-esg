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
