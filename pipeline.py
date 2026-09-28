"""
pipeline.py

Top-level entry point:

    Image -> preprocess (by type) -> OCR (text + coordinates)
          -> field/table extraction -> normalization -> schema (dict/JSON)

Usage:
    from ocr_pipeline.pipeline import process_document

    result = process_document("sample_1_scanned_credit_report.png", doc_type="scanned")
    print(json.dumps(result, indent=2))

doc_type is one of: "scanned", "photo", "screenshot"
If you don't know the type ahead of time, use classify_doc_type() as a rough guess.
"""

import json
import cv2
import numpy as np

from .preprocess import preprocess, to_gray
from .ocr import ocr_to_lines, run_ocr, average_confidence
from .extract import extract_fields
from .normalize import build_schema
from .classify import classify_document
from .quality import assess_image_quality


def classify_doc_type(img) -> str:
    """
    Very rough heuristic classifier so the pipeline can pick a preprocessing
    path automatically. In production, replace this with a small trained
    classifier (or just ask the upload UI what kind of file it is).

    Heuristics:
        - Screenshots: near-perfect edges, very few unique colors, sharp gradients
        - Photos: high color variance, background outside a document boundary
        - Scanned: mostly grayscale/white background already, low color variance
    """
    if len(img.shape) == 2:
        return "scanned"

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    sat_mean = saturation.mean()

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # fraction of near-white pixels (typical of a scan filling the whole frame)
    white_frac = float(np.mean(gray > 200))

    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.mean(edges > 0))

    if white_frac > 0.55 and sat_mean < 20:
        return "scanned"
    if sat_mean < 35 and edge_density < 0.05:
        return "screenshot"
    return "photo"


def process_document(image_path: str, doc_type: str = None, lang: str = "eng", psm: int = 6) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")
    return process_image(img, doc_type=doc_type, lang=lang, psm=psm)


def process_image(img: np.ndarray, doc_type: str = None, lang: str = "eng", psm: int = 6) -> dict:
    """
    Same as process_document(), but takes an already-loaded image (a numpy
    BGR array, as cv2.imread or cv2.cvtColor(pil_to_array(...)) would give
    you) instead of a file path. process_document() is just this function
    plus a cv2.imread() in front of it - this split exists so PDF pages
    (rendered directly into memory, one per page, no image file involved)
    can run through the exact same pipeline without a round-trip through
    a temp file. See pdf_support.py.
    """
    if doc_type is None:
        doc_type = classify_doc_type(img)

    # Cheap pixel-level quality check BEFORE the expensive OCR step, run on
    # the raw input (not the preprocessed version) since we want to know
    # about the actual capture quality, not how well preprocessing masked it.
    raw_gray = to_gray(img)
    quality = assess_image_quality(raw_gray)

    processed = preprocess(img, doc_type)

    lines = ocr_to_lines(processed, lang=lang, psm=psm)
    words = run_ocr(processed, lang=lang, psm=psm)  # for confidence scoring
    conf = average_confidence(words)

    extraction = extract_fields(lines)

    full_text = "\n".join(l.text for l in lines)
    category_result = classify_document(full_text)

    schema = build_schema(extraction, doc_type, conf, document_category=category_result)
    schema["image_quality"] = quality

    # A severely-degraded source image should be flagged even if, by luck,
    # OCR confidence and field extraction came back looking fine -
    # low-quality input can produce confidently-wrong text, not just
    # low-confidence text.
    if quality["recommend_reject"]:
        schema["validation"]["needs_review"] = True
        schema["validation"].setdefault("quality_warnings", []).extend(quality["issues"])

    # keep the raw OCR lines available for debugging/audit trail
    schema["_debug"] = {
        "detected_doc_type": doc_type,
        "raw_lines": [l.text for l in lines],
    }
    return schema


def process_document_to_json(image_path: str, doc_type: str = None, **kwargs) -> str:
    return json.dumps(process_document(image_path, doc_type=doc_type, **kwargs), indent=2, ensure_ascii=False)


