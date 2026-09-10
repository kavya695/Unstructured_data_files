"""Export the bundled sample images to one clean CSV file."""

import argparse
from pathlib import Path

from .cli import _result_to_row, _write_csv
from .pipeline import process_document
from .run_samples import SAMPLES, SAMPLES_DIR


def main():
    parser = argparse.ArgumentParser(description="Export OCR results to CSV")
    parser.add_argument(
        "--output",
        default=str(SAMPLES_DIR / "sample_extracted_data.csv"),
        help="CSV output path; defaults to the ocr_pipeline folder",
    )
    args = parser.parse_args()

    rows = []
    for filename, doc_type in SAMPLES:
        image_path = SAMPLES_DIR / filename
        if not image_path.exists():
            print(f"Skipped missing sample: {image_path}")
            continue
        result = process_document(str(image_path), doc_type=doc_type)
        rows.append(_result_to_row(result, filename))

    if not rows:
        raise FileNotFoundError("No sample images were found")

    output_path = Path(args.output)
    _write_csv(rows, output_path)
    print(f"CSV written to {output_path.resolve()}")


if __name__ == "__main__":
    main()