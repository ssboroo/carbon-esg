"""Controlled ingestion of official Mongolian legal texts.

This module deliberately does not scrape or infer legal status. A reviewed source
adapter supplies the consolidated official text and structured provision boundaries.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalAct, LegalActVersion, LegalProvision

ALLOWED_HOSTS = {"legalinfo.mn", "www.legalinfo.mn"}
LEGAL_STATUSES = {
    "in_force", "not_yet_effective", "repealed", "draft",
    "consultation", "needs_verification",
}


def validate_official_source(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Legal text must be sourced from an official HTTPS Legalinfo URL")
    return url


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ingest_consolidated_act(
    db: Session,
    *,
    official_identifier: str,
    title_mn: str,
    document_type: str,
    domain: str,
    legal_status: str,
    official_source_url: str,
    version_label: str,
    full_text: str,
    provisions: list[dict],
    effective_from: date | None = None,
    promulgated_on: date | None = None,
    verification_note: str,
) -> LegalActVersion:
    """Persist an explicitly reviewed consolidated act and its provision structure.

    Call only after a human has verified that full_text is the current official
    consolidated text, not a bill, amendment-only text, or repealed version.
    """
    validate_official_source(official_source_url)
    if legal_status not in LEGAL_STATUSES:
        raise ValueError("Unsupported legal status")
    if not verification_note.strip():
        raise ValueError("A human verification note is required")
    if not full_text.strip():
        raise ValueError("Full legal text is required")
    if not provisions:
        raise ValueError("At least one structured provision is required")
    for item in provisions:
        if not item.get("provision_code") or not item.get("full_text", "").strip():
            raise ValueError("Every provision requires a code and full text")

    act = db.scalar(select(LegalAct).where(
        LegalAct.jurisdiction == "MN",
        LegalAct.official_identifier == official_identifier,
    ))
    if act is None:
        act = LegalAct(
            jurisdiction="MN", official_identifier=official_identifier,
            title_mn=title_mn, document_type=document_type, domain=domain,
            legal_status=legal_status, official_source_url=official_source_url,
            promulgated_on=promulgated_on, effective_from=effective_from,
            last_verified_at=datetime.now(timezone.utc),
            verification_note=verification_note,
        )
        db.add(act)
        db.flush()
    else:
        act.title_mn = title_mn
        act.document_type = document_type
        act.domain = domain
        act.legal_status = legal_status
        act.official_source_url = official_source_url
        act.promulgated_on = promulgated_on
        act.effective_from = effective_from
        act.last_verified_at = datetime.now(timezone.utc)
        act.verification_note = verification_note

    digest = sha256_text(full_text)
    existing = db.scalar(select(LegalActVersion).where(
        LegalActVersion.legal_act_id == act.id,
        LegalActVersion.version_label == version_label,
    ))
    if existing is not None:
        if existing.content_sha256 != digest:
            raise ValueError("Version label exists with different content; create a new version label")
        return existing

    version = LegalActVersion(
        legal_act_id=act.id, version_label=version_label,
        source_url=official_source_url, retrieved_at=datetime.now(timezone.utc),
        full_text=full_text, content_sha256=digest,
        is_official_consolidated_text=True,
        change_summary="Human-reviewed official consolidated text import",
    )
    db.add(version)
    db.flush()

    ids = {}
    for item in provisions:
        parent_code = item.get("parent_code")
        parent_id = ids.get(parent_code) if parent_code else None
        if parent_code and parent_id is None:
            raise ValueError("Parent article must be imported before its clause")
        row = LegalProvision(
            legal_act_version_id=version.id,
            parent_provision_id=parent_id,
            provision_code=item["provision_code"],
            heading=item.get("heading"),
            full_text=item["full_text"],
            effective_from=item.get("effective_from"),
            effective_to=item.get("effective_to"),
            content_sha256=sha256_text(item["full_text"]),
        )
        db.add(row)
        db.flush()
        if not parent_code:
            ids[item["provision_code"]] = row.id
    db.flush()
    return version
