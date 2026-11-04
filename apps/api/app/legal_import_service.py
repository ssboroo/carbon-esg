from app.legal_parser import parse_articles_and_clauses
from app.legal_source_fetch import extract_legal_text, fetch_official_html


def load_legal_source(url: str):
    """Fetch official HTML and return extracted text plus provision candidates."""
    html = fetch_official_html(url)
    text = extract_legal_text(html)
    return text, parse_articles_and_clauses(text)
