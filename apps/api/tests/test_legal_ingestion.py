import pytest

from app.legal_ingestion import sha256_text, validate_official_source


def test_only_official_legalinfo_https_sources_are_accepted():
    assert validate_official_source("https://legalinfo.mn/mn/detail/8935").startswith("https://")
    with pytest.raises(ValueError):
        validate_official_source("http://legalinfo.mn/mn/detail/8935")
    with pytest.raises(ValueError):
        validate_official_source("https://example.com/law")


def test_full_text_checksum_is_stable_and_content_sensitive():
    assert sha256_text("Хууль") == sha256_text("Хууль")
    assert sha256_text("Хууль") != sha256_text("Хууль ")
