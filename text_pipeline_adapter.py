"""Adapt the existing batch text pipeline for the upload UI."""
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_path in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from backend.main import run_pipeline
from extractors.pdf_extractor import _page_has_text
import fitz


def is_text_pdf(input_path: str | Path) -> bool:
    document = fitz.open(input_path)
    try:
        return bool(document.page_count) and all(
            _page_has_text(page) for page in document
        )
    finally:
        document.close()


def process_text_document(
    input_path: str | Path,
    original_name: str,
    output_path: str | Path,
) -> dict:
    input_path = Path(input_path)
    result = run_pipeline(
        [str(input_path)],
        out_path=str(output_path),
        document_labels={str(input_path): original_name},
    )
    document = result["schemas_by_document"][original_name]
    confidence = document.get("type_confidence", 0.0)

    return {
        "processing_type": "text",
        "source_type": "text",
        "document_category": {
            "category": document.get("document_type", "unknown"),
            "method": "keyword_and_field_scoring",
            "confidence": confidence,
        },
        "fields": document.get("examples", {}),
        "schema": document.get("schema", {}),
        "transactions": [],
        "_debug": {"detected_doc_type": "text_document"},
    }