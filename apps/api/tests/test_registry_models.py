import json
from pathlib import Path

from app.models import Base, LegalAct, LegalActVersion, LegalProvision, Standard


def test_registry_models_are_registered_in_metadata():
    expected = {"legal_acts", "legal_act_versions", "legal_provisions",
                "compliance_requirements", "standards", "standard_versions"}
    assert expected.issubset(set(Base.metadata.tables))


def test_mongolian_seed_catalogs_have_official_sources():
    root = Path(__file__).resolve().parents[1]
    legal = json.loads((root / "data" / "legal_registry_mn_seed.json").read_text(encoding="utf-8"))
    standards = json.loads((root / "data" / "standards_registry_seed.json").read_text(encoding="utf-8"))
    assert len(legal["records"]) >= 20
    assert len(standards["records"]) >= 8
    assert all(x["official_url"].startswith("https://legalinfo.mn/") for x in legal["records"])
    assert all(x["source_url"].startswith("https://") for x in standards["records"])
