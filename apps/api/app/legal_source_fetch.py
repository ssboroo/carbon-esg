"""Official Legalinfo source retrieval and conservative article parser."""
import re
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

ALLOWED_HOSTS = {"legalinfo.mn", "www.legalinfo.mn"}
ARTICLE_RE = re.compile(r"^\s*(\d{1,3})\s*дугаар\s+зүйл\s*[.\-:–]?\s*(.*)$", re.I)
CLAUSE_RE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3})+)\s*[.)]?\s*(.*)$")


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Only official HTTPS Legalinfo URLs are allowed")


def fetch_official_html(url: str) -> str:
    validate_source_url(url)
    with httpx.Client(timeout=20.0, follow_redirects=True, headers={
        "User-Agent": "CarbonESG-LegalRegistry/0.1"
    }) as client:
        response = client.get(url)
        response.raise_for_status()
        validate_source_url(str(response.url))
        if "text/html" not in response.headers.get("content-type", ""):
            raise ValueError("The official source did not return HTML")
        if len(response.content) > 15 * 1024 * 1024:
            raise ValueError("Source page exceeds the configured import size limit")
        return response.text


def extract_legal_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "header", "footer", "form", "button", "svg"]):
        node.decompose()
    candidates = soup.find_all(["main", "article", "section", "div"]) or [soup.body or soup]
    best_text, best_score = "", -1
    for node in candidates:
        lines = [x.strip() for x in node.get_text("\n").splitlines() if x.strip()]
        candidate = "\n".join(lines)
        articles = len(re.findall(r"(?im)^\d{1,3}\s*дугаар\s+зүйл", candidate))
        clauses = len(re.findall(r"(?m)^\d{1,3}\.\d+(?:\.\d+)?\s", candidate))
        score = articles * 100 + clauses + min(len(candidate) // 1000, 100)
        if score > best_score:
            best_text, best_score = candidate, score
    if len(best_text) < 1000 or best_score < 100:
        raise ValueError("Legal text container was not identified reliably")
    return best_text
