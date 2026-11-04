"""Idempotently load the Mongolian legal and standards discovery catalogs.

Run from apps/api after setting DATABASE_URL:
  python -m scripts.seed_legal_registry
This loads metadata only. It does not claim that full texts have been imported.
"""
import json
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import LegalAct, Standard

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def seed_legal_acts(db):
    data = json.loads((DATA_DIR / "legal_registry_mn_seed.json").read_text(encoding="utf-8"))
    inserted = updated = 0
    for item in data["records"]:
        row = db.scalar(select(LegalAct).where(
            LegalAct.jurisdiction == "MN",
            LegalAct.official_identifier == item["code"],
        ))
        # Never promote an unverified discovery entry to an authoritative legal status.
        source_status = item.get("status", "needs_verification")
        status = source_status if source_status in {
            "in_force", "not_yet_effective", "repealed", "draft", "consultation"
        } else "needs_verification"
        if row is None:
            row = LegalAct(
                jurisdiction="MN",
                official_identifier=item["code"],
                title_mn=item["title_mn"],
                document_type=item["type"],
                domain=item["domain"],
                legal_status=status,
                official_source_url=item["official_url"],
                verification_note="Discovery seed only; verify current consolidated text and legal status.",
            )
            db.add(row)
            inserted += 1
        else:
            row.title_mn = item["title_mn"]
            row.document_type = item["type"]
            row.domain = item["domain"]
            row.official_source_url = item["official_url"]
            if row.legal_status == "needs_verification":
                row.legal_status = status
            updated += 1
    return inserted, updated


def seed_standards(db):
    data = json.loads((DATA_DIR / "standards_registry_seed.json").read_text(encoding="utf-8"))
    inserted = updated = 0
    for item in data["records"]:
        jurisdiction = "MN" if item["code"].startswith("MNS ") else "INTL"
        row = db.scalar(select(Standard).where(
            Standard.jurisdiction == jurisdiction,
            Standard.standard_code == item["code"],
        ))
        if row is None:
            db.add(Standard(
                jurisdiction=jurisdiction,
                standard_code=item["code"],
                title_mn=item["title_mn"],
                publisher=item["publisher"],
                domain=item["domain"],
                status=item["status"],
                official_catalog_url=item["source_url"],
                license_required=item.get("license_required", True),
                notes=item.get("notes"),
            ))
            inserted += 1
        else:
            row.title_mn = item["title_mn"]
            row.publisher = item["publisher"]
            row.domain = item["domain"]
            row.status = item["status"]
            row.official_catalog_url = item["source_url"]
            row.notes = item.get("notes")
            updated += 1
    return inserted, updated


def main():
    if SessionLocal is None:
        raise RuntimeError("Set DATABASE_URL before seeding the legal registry")
    with SessionLocal() as db:
        try:
            legal = seed_legal_acts(db)
            standards = seed_standards(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
    print({
        "legal_acts_inserted_updated": legal,
        "standards_inserted_updated": standards,
        "note": "Metadata only; official full texts still require verified ingestion.",
    })


if __name__ == "__main__":
    main()
