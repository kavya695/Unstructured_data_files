"""Export all bundled sample OCR results to one JSON file."""

import argparse
import json
from pathlib import Path

from .pipeline import process_document
from .run_samples import SAMPLES, SAMPLES_DIR


def main():
    parser = argparse.ArgumentParser(description="Export OCR results to JSON")
    parser.add_argument(
        "--output",
        default=str(SAMPLES_DIR / "all_samples_result.json"),
        help="JSON output path; defaults to the ocr_pipeline folder",
    )
    args = parser.parse_args()

    results = []
    for filename, doc_type in SAMPLES:
        image_path = SAMPLES_DIR / filename
        if not image_path.exists():
            print(f"Skipped missing sample: {image_path}")
            continue
        results.append(
            {
                "source_file": filename,
                "document_type": doc_type,
                "result": process_document(str(image_path), doc_type=doc_type),
            }
        )

    if not results:
        raise FileNotFoundError("No sample images were found")

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)
        file.write("\n")
    print(f"JSON written to {output_path.resolve()}")


if __name__ == "__main__":
    main()