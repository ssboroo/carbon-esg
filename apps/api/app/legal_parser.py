import re

ARTICLE_RE = re.compile(r"^\s*(\d{1,3})\s*(?:дүгээр|дугаар)\s+зүйл\s*[.\-:–]?\s*(.*)$", re.I)
CLAUSE_RE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3})+)\s*[.)]?\s*(.*)$")


def parse_articles_and_clauses(full_text: str) -> list[dict]:
    lines = full_text.splitlines()
    result = []
    current = None
    heading = ""
    body = []

    def flush():
        if current is None:
            return
        parent_code = str(current)
        result.append({"provision_code": parent_code, "heading": heading or None, "full_text": "\n".join(body).strip()})
        code = None
        chunk = []
        for line in body:
            match = CLAUSE_RE.match(line)
            if match:
                if code is not None:
                    result.append({"provision_code": code, "parent_code": parent_code, "heading": None, "full_text": "\n".join(chunk).strip()})
                code, chunk = match.group(1), [line]
            elif code is not None:
                chunk.append(line)
        if code is not None:
            result.append({"provision_code": code, "parent_code": parent_code, "heading": None, "full_text": "\n".join(chunk).strip()})

    for line in lines:
        match = ARTICLE_RE.match(line)
        if match:
            flush()
            current, heading, body = int(match.group(1)), match.group(2).strip(), [line]
        elif current is not None:
            body.append(line)
    flush()
    if sum(1 for row in result if "parent_code" not in row) < 3:
        raise ValueError("Could not detect at least three article headings")
    return result
