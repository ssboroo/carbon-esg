from app.legal_parser import parse_articles_and_clauses
from app.legal_source_fetch import extract_legal_text, fetch_official_html


def load_legal_source(url: str):
    """Fetch official HTML and return extracted text plus provision candidates."""
    html = fetch_official_html(url)
    text = extract_legal_text(html)
    return text, parse_articles_and_clauses(text)


def import_reviewed_act(db, *, code: str, title: str, url: str, version: str,
                        document_type: str, domain: str, status: str,
                        verification_note: str, effective_from=None, promulgated_on=None):
    """Fetch, parse and persist a source after an authorized reviewer approves it."""
    from app.legal_ingestion import ingest_consolidated_act
    from app.legal_source_fetch import validate_source_url
    validate_source_url(url)
    full_text, parsed = load_legal_source(url)
    flat_provisions = [
        {key: value for key, value in item.items() if key != "parent_code"}
        for item in parsed
    ]
    return ingest_consolidated_act(
        db,
        official_identifier=code,
        title_mn=title,
        document_type=document_type,
        domain=domain,
        legal_status=status,
        official_source_url=url,
        version_label=version,
        full_text=full_text,
        provisions=flat_provisions,
        effective_from=effective_from,
        promulgated_on=promulgated_on,
        verification_note=verification_note,
    )
