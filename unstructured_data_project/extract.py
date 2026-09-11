"""
Stage 1: file -> raw text, dispatched by extension (PDF / Word / Email)
Stage 2: light cleaning / normalization

Every extractor returns list[str] ("pages"). This module turns that into a
flat list[dict] of {'page', 'line'} — the shape every downstream stage
(chunk.py, tfidf_cluster.py, schema_infer.py) already expects. Add a new
format by writing one function that returns list[str] and registering its
extension below; nothing else in the pipeline has to change.
"""
import re
from pathlib import Path

from extractors.pdf_extractor import extract_pdf
from extractors.docx_extractor import extract_docx
from extractors.email_extractor import extract_eml, extract_msg


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".eml": extract_eml,
    ".msg": extract_msg,
    ".txt": lambda path: [Path(path).read_text(errors="ignore")],
}


def extract_text(path: str) -> list[str]:
    """Return a list of page/section strings for any supported file type."""
    ext = Path(path).suffix.lower()
    if ext not in EXTRACTORS:
        raise ValueError(
            f"Unsupported file type '{ext}' for {path}. "
            f"Supported: {sorted(EXTRACTORS)}. "
            f"(.doc files: convert to .docx first, e.g. via LibreOffice "
            f"--headless --convert-to docx)"
        )
    return EXTRACTORS[ext](path)


def clean_line(line: str) -> str:
    """Preserve 'LABEL: VALUE' structure (colons, casing); only collapse
    whitespace and strip OCR table-rule artifacts. Aggressive normalization
    (lowercasing etc.) happens only at the TF-IDF stage."""
    line = re.sub(r'[ \t]+', ' ', line)
    line = line.replace('|', ' ') if line.count('|') > 3 else line  # OCR table rules, not docx table separators
    return line.strip()


def extract_and_clean(path: str) -> list[dict]:
    """Return [{'page': i, 'line': text, 'source': path}, ...] for every
    non-empty line, for ANY supported file type."""
    pages = extract_text(path)
    out = []
    for i, page_text in enumerate(pages, start=1):
        for raw_line in page_text.split('\n'):
            cleaned = clean_line(raw_line)
            if cleaned:
                out.append({"page": i, "line": cleaned, "source": path})
    return out


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "../sample.pdf"
    lines = extract_and_clean(target)
    print(f"Extracted {len(lines)} non-empty lines from {target}\n")
    for l in lines[:30]:
        print(l["page"], repr(l["line"]))