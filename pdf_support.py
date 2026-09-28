"""
pdf_support.py

Adds multi-page PDF input to the pipeline without changing anything about
how single images already work:

    PDF file -> split into per-page images -> process_image() on each page
             -> merge all pages' results into one combined schema

Install (one extra Python package + one system dependency):
    pip install pdf2image
    # Windows: also install poppler and add its /bin folder to PATH:
    #   https://github.com/oschwartz10612/poppler-windows/releases
    # Linux:   sudo apt-get install poppler-utils
    # Mac:     brew install poppler

Usage:
    from ocr_pipeline.pdf_support import process_pdf

    result = process_pdf("credit_report.pdf", doc_type="scanned")
    print(result["fields"]["current_balance"])
    print(len(result["transactions"]))       # transactions from ALL pages, combined
    print(result["_pdf_debug"]["page_count"])
"""

import cv2
import numpy as np
from typing import List, Dict, Optional

from .pipeline import process_image
from .normalize import REQUIRED_FIELDS_BY_CATEGORY


def _pil_to_cv2(pil_img) -> np.ndarray:
    """pdf2image gives back PIL images (RGB); the rest of the pipeline
    (preprocess.py, ocr.py) expects OpenCV's BGR numpy array format,
    same as cv2.imread() would produce - so convert once here."""
    rgb = np.array(pil_img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
    """
    Renders every page of a PDF to an image, highest quality first.
    dpi=300 is a good default: high enough for small print/fine text,
    without being so large that OCR gets slow. Bump to 400+ only if you're
    still missing small text after checking preprocessing.
    """
    from pdf2image import convert_from_path  # imported lazily so this whole
    # module still loads fine even if pdf2image/poppler aren't installed,
    # for people who only ever process single images.

    pil_pages = convert_from_path(pdf_path, dpi=dpi)
    return [_pil_to_cv2(p) for p in pil_pages]


def _merge_field_dicts(per_page_fields: List[Dict]) -> Dict:
    """
    Combines the 'fields' dict from every page into one. Rule: first
    non-null value wins for each key - e.g. if 'account_number' is found
    on page 1 and page 2 (header repeated on every page, common in real
    statements), we just keep whichever page found it first, since it
    should be the same value either way.
    """
    if not per_page_fields:
        return {}
    merged = dict(per_page_fields[0])  # start with all known keys, page 1's values
    for page_fields in per_page_fields[1:]:
        for key, value in page_fields.items():
            if merged.get(key) is None and value is not None:
                merged[key] = value
    return merged


def _pick_document_category(per_page_categories: List[Dict]) -> Dict:
    """
    Different pages of the same document can classify slightly differently
    (e.g. a transactions-only page has fewer distinctive keywords than the
    summary page). We trust whichever single page produced the highest
    confidence, rather than averaging across pages - a table-only page
    correctly saying "no strong signal" shouldn't drag down a confident
    match found elsewhere in the same PDF.
    """
    if not per_page_categories:
        return {"category": "unknown", "method": "none", "confidence": 0.0, "matched_phrases": []}
    return max(per_page_categories, key=lambda c: c.get("confidence", 0.0))


def process_pdf(pdf_path: str, doc_type: Optional[str] = None, dpi: int = 300,
                 lang: str = "eng", psm: int = 6) -> Dict:
    """
    Main entry point for PDF input. Returns the same schema shape as
    process_document()/process_image() for a single image, so downstream
    code doesn't need to know or care whether the original input was a
    PDF or a plain image - the only addition is a "_pdf_debug" block.
    """
    images = pdf_to_images(pdf_path, dpi=dpi)
    if not images:
        raise ValueError(f"No pages could be rendered from {pdf_path}")

    page_results = [
        process_image(img, doc_type=doc_type, lang=lang, psm=psm)
        for img in images
    ]

    merged_fields_raw = _merge_field_dicts([p["fields"] for p in page_results])
    merged_transactions = [t for p in page_results for t in p["transactions"]]
    merged_category = _pick_document_category([p["document_category"] for p in page_results])
    avg_confidence = sum(p["ocr_confidence"] for p in page_results) / len(page_results)

    category = merged_category.get("category", "unknown")
    required = REQUIRED_FIELDS_BY_CATEGORY.get(category, REQUIRED_FIELDS_BY_CATEGORY["unknown"])
    missing = [f for f in required if merged_fields_raw.get(f) is None]

    return {
        "source_type": page_results[0]["source_type"],
        "document_category": merged_category,
        "ocr_confidence": round(avg_confidence, 1),
        "fields": merged_fields_raw,
        "transactions": merged_transactions,
        "validation": {
            "missing_required_fields": missing,
            "needs_review": bool(missing) or avg_confidence < 60.0,
        },
        "_pdf_debug": {
            "page_count": len(images),
            "per_page_categories": [p["document_category"] for p in page_results],
            "per_page_ocr_confidence": [p["ocr_confidence"] for p in page_results],
        },
    }


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else None
    dtype = sys.argv[2] if len(sys.argv) > 2 else None
    if not path:
        print("Usage: python3 -m ocr_pipeline.pdf_support <pdf_path> [scanned|photo|screenshot]")
        sys.exit(1)
    result = process_pdf(path, doc_type=dtype)
    print(json.dumps(result, indent=2, ensure_ascii=False))