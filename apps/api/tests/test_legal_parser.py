from app.legal_parser import parse_articles_and_clauses


def test_parser_extracts_articles_and_numbered_clauses():
    text = """НЭГДҮГЭЭР БҮЛЭГ
1 дүгээр зүйл. Зорилго
1.1. Энэ хуулийн зорилго.
1.2. Хуулийн хүрээ.
2 дугаар зүйл. Үүрэг
2.1. Байгууллага тайлагнана.
"""
    rows = parse_articles_and_clauses(text)
    codes = [row["provision_code"] for row in rows]
    assert codes == ["1", "1.1", "1.2", "2", "2.1"]
    assert rows[1]["parent_code"] == "1"


def test_parser_rejects_non_legal_text():
    try:
        parse_articles_and_clauses("Энгийн тайлбар, зүйл заалт байхгүй.")
    except ValueError:
        return
    raise AssertionError("Expected parser to reject unstructured text")
