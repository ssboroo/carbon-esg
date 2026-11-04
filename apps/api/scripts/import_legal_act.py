import argparse
from datetime import date
from app.database import SessionLocal
from app.legal_import_service import import_reviewed_act

p = argparse.ArgumentParser(description="Import a reviewed official Legalinfo act")
p.add_argument("--code", required=True)
p.add_argument("--title", required=True)
p.add_argument("--url", required=True)
p.add_argument("--version", required=True)
p.add_argument("--domain", required=True)
p.add_argument("--status", default="needs_verification")
p.add_argument("--note", required=True)
p.add_argument("--human-reviewed", action="store_true")
a = p.parse_args()
if not a.human_reviewed:
    p.error("A human must review the consolidated source before import")
if SessionLocal is None:
    raise RuntimeError("DATABASE_URL is required")
with SessionLocal() as db:
    try:
        v = import_reviewed_act(db, code=a.code, title=a.title, url=a.url,
            version=a.version, document_type="law", domain=a.domain,
            status=a.status, verification_note=a.note)
        db.commit()
        print({"version_id": str(v.id), "sha256": v.content_sha256})
    except Exception:
        db.rollback()
        raise
