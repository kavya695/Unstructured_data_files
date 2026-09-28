"""Word (.docx) -> list[str] (one string per 'page' — Word has no real page
breaks in the XML, so we treat the WHOLE document as one page, plus we also
split out each table as its own page so table rows don't get mashed into
paragraph text)."""
from docx import Document


def extract_docx(path: str) -> list[str]:
    doc = Document(path)
    pages = []

    # Body paragraphs (in order, including headings)
    para_lines = [p.text for p in doc.paragraphs if p.text.strip()]
    if para_lines:
        pages.append("\n".join(para_lines))

    # Tables: each table becomes its own "page" so schema_infer's
    # Label: Value regex isn't confused by paragraph text mixed with cells
    for t_idx, table in enumerate(doc.tables):
        table_lines = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            table_lines.append(" | ".join(cells))
        if table_lines:
            pages.append("\n".join(table_lines))

    return pages
