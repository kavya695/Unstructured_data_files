"""
run_samples.py

Quick demo: runs the full pipeline on the 3 sample images and prints the
resulting schema for each. Run from the directory containing both this
package and the sample_*.png files:

    python3 -m ocr_pipeline.run_samples
"""
import json
from pathlib import Path
from .pipeline import process_document

# Resolve sample image paths relative to this file's own location, so this
# script works no matter what directory you run it from.
SAMPLES_DIR = Path(__file__).parent

SAMPLES = [
    ("sample_1_scanned_credit_report.png", "scanned"),
    ("sample_2_document_photo.png", "photo"),
    ("sample_3_financial_report_screenshot.png", "screenshot"),
    ("sample_4_invoice.png", "scanned"),
    ("sample_5_bank_statement.png", "scanned"),
]

if __name__ == "__main__":
    for filename, doc_type in SAMPLES:
        path = SAMPLES_DIR / filename
        print(f"\n{'=' * 70}\n{filename}  (doc_type={doc_type})\n{'=' * 70}")
        try:
            result = process_document(str(path), doc_type=doc_type)
            result.pop("_debug", None)  # drop raw OCR lines for a cleaner demo view
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except FileNotFoundError as e:
            print(f"  Skipped: {e}")
