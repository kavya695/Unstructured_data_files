"""
Stage 3: split the flat line list into chunks (sections) that TF-IDF and
clustering can compare against each other.

Strategy: a new chunk starts whenever we hit an ALL-CAPS heading-like line
(e.g. "ADDRESS (ES):", "ACCOUNT(S)", "ENQUIRIES") or a page break. This is a
simple heuristic, but it's exactly the kind of thing you'd tune per document
family. For documents with no visual headings, chunk by fixed line-count
windows instead (see `chunk_by_window` below).
"""
import re


HEADING_RE = re.compile(r'^[A-Z][A-Z0-9 /()&:,.\-]{3,}$')


def looks_like_heading(line: str) -> bool:
    letters = re.sub(r'[^A-Za-z]', '', line)
    if len(letters) < 4:
        return False
    return bool(HEADING_RE.match(line)) and letters.isupper()


def chunk_by_heading(lines: list[dict]) -> list[dict]:
    """lines: [{'page':int, 'line':str}, ...] -> [{'title':str, 'text':str, 'page':int}]"""
    chunks = []
    current_title = "HEADER"
    current_lines = []
    start_page = lines[0]["page"] if lines else 1

    def flush():
        if current_lines:
            chunks.append({
                "title": current_title,
                "text": " ".join(current_lines),
                "page": start_page,
            })

    for item in lines:
        if looks_like_heading(item["line"]):
            flush()
            current_title = item["line"]
            current_lines = []
            start_page = item["page"]
        else:
            current_lines.append(item["line"])
    flush()
    return [c for c in chunks if c["text"].strip()]


def chunk_by_window(lines: list[dict], window: int = 8) -> list[dict]:
    """Fallback for documents with no visual headings: fixed-size windows."""
    chunks = []
    for i in range(0, len(lines), window):
        window_lines = lines[i:i + window]
        chunks.append({
            "title": f"chunk_{i // window}",
            "text": " ".join(l["line"] for l in window_lines),
            "page": window_lines[0]["page"],
        })
    return chunks


if __name__ == "__main__":
    from extract import extract_and_clean
    lines = extract_and_clean("../sample.pdf")
    chunks = chunk_by_heading(lines)
    print(f"{len(chunks)} chunks found\n")
    for c in chunks:
        print(f"--- [{c['title']}] (page {c['page']}) ---")
        print(c["text"][:150])
        print()
