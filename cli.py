"""
cli.py

Command-line entry point for running the pipeline on a single image.

This file exists ONLY to be run directly - unlike pipeline.py, it is never
imported by __init__.py, so `python -m ocr_pipeline.cli` doesn't trigger
Python's "module found in sys.modules after import of package" warning.
(That warning happened because pipeline.py used to have its own
__main__ block, and __init__.py separately imports pipeline.py too -
Python loaded it twice, once as part of the package and once as the
directly-run script. cli.py sidesteps that by being a plain, standalone
script the package itself never touches.)

Usage:
    python -m ocr_pipeline.cli <image_path> [scanned|photo|screenshot] [output.csv]
"""
import csv
import json
import sys
from pathlib import Path

from .pipeline import process_document


def _flatten_dict(value, prefix=""):
    """Flatten nested dictionaries; keep lists intact as JSON cells."""
    flattened = {}
    for key, item in value.items():
        column = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(_flatten_dict(item, column))
        elif isinstance(item, list):
            flattened[column] = json.dumps(item, ensure_ascii=False)
        else:
            flattened[column] = item
    return flattened


def _result_to_row(result, source_name=""):
    row = {"source_file": source_name}
    row.update(result.get("fields", {}))
    row["source_type"] = result.get("source_type", "")
    category = result.get("document_category", {})
    row["document_category"] = category.get("category", "")
    row["category_confidence"] = category.get("confidence", "")
    row["ocr_confidence"] = result.get("ocr_confidence", "")
    row["transactions"] = json.dumps(result.get("transactions", []), ensure_ascii=False)
    validation = result.get("validation", {})
    row["missing_required_fields"] = json.dumps(
        validation.get("missing_required_fields", []), ensure_ascii=False
    )
    row["needs_review"] = validation.get("needs_review", "")
    return row


def _write_csv(rows, output_path):
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    dtype = sys.argv[2] if len(sys.argv) > 2 else None
    output_path = sys.argv[3] if len(sys.argv) > 3 else Path(__file__).parent / "extracted_data.csv"
    if not path:
        print("Usage: python -m ocr_pipeline.cli <image_path> [scanned|photo|screenshot] [output.csv]")
        sys.exit(1)
    result = process_document(path, doc_type=dtype)
    _write_csv([_result_to_row(result, Path(path).name)], Path(output_path))
    print(f"CSV written to {Path(output_path).resolve()}")


if __name__ == "__main__":
    main()