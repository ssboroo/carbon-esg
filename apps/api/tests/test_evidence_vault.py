import io
import zipfile

import pytest
from fastapi import HTTPException

from app.evidence_vault import (
    MAX_EVIDENCE_BYTES,
    detect_evidence_type,
    safe_filename,
    scan_with_clamav,
)


def test_filename_is_sanitized_and_path_components_are_removed():
    assert safe_filename("../../secret file.pdf") == "secret file.pdf"
    assert '"' not in safe_filename('bad"name.pdf')


def test_pdf_requires_matching_signature():
    assert detect_evidence_type("report.pdf", b"%PDF-1.7\nbody") == "application/pdf"
    with pytest.raises(HTTPException) as error:
        detect_evidence_type("report.pdf", b"not a pdf")
    assert error.value.status_code == 415


def test_image_requires_matching_signature():
    assert detect_evidence_type("image.png", b"\x89PNG\r\n\x1a\nrest") == "image/png"
    with pytest.raises(HTTPException):
        detect_evidence_type("image.png", b"plain text")


def test_csv_requires_utf8_and_nonempty_content():
    assert detect_evidence_type("activity.csv", b"date,kwh\n2026-01-01,10") == "text/csv"
    with pytest.raises(HTTPException):
        detect_evidence_type("activity.csv", b"\xff\xfe")
    with pytest.raises(HTTPException):
        detect_evidence_type("activity.csv", b"\x00")


def test_xlsx_requires_expected_workbook_entries():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    assert detect_evidence_type("activity.xlsx", buffer.getvalue()) == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    with pytest.raises(HTTPException):
        detect_evidence_type("activity.xlsx", b"not a zip")


def test_unsupported_extensions_are_rejected():
    with pytest.raises(HTTPException) as error:
        detect_evidence_type("script.html", b"<script>alert(1)</script>")
    assert error.value.status_code == 415


def test_malware_scanning_fails_closed_when_not_configured(monkeypatch):
    monkeypatch.delenv("CLAMAV_HOST", raising=False)
    with pytest.raises(HTTPException) as error:
        scan_with_clamav(b"%PDF-1.7")
    assert error.value.status_code == 503


def test_upload_size_limit_is_fifteen_megabytes():
    assert MAX_EVIDENCE_BYTES == 15 * 1024 * 1024
