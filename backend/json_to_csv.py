"""Stage 9: schema_output.json -> one-row-per-document CSV."""
import sys
import json
import csv
from pathlib import Path


BASE_DIR = Path(__file__).parent
DEFAULT_JSON_PATH = BASE_DIR / "output" / "schema_output.json"
DEFAULT_CSV_PATH = BASE_DIR / "output" / "schema_output.csv"


def flatten_to_rows(data: dict) -> list[dict]:
    """Flatten nested output into one row per document.

    The field names become CSV columns so a document with many discovered
    fields does not produce many rows. Multiple values for one field are kept
    in the same cell, separated by semicolons.
    """
    rows = []
    field_names = []
    for doc_path, doc_info in data.get("schemas_by_document", {}).items():
        properties = doc_info.get("schema", {}).get("properties", {})
        for field_name in properties:
            if field_name not in field_names:
                field_names.append(field_name)

    for doc_path, doc_info in data.get("schemas_by_document", {}).items():
        properties = doc_info.get("schema", {}).get("properties", {})
        examples = doc_info.get("examples", {})
        row = {
            "document": doc_path,
            "document_type": doc_info.get("document_type", "unknown"),
            "type_confidence": doc_info.get("type_confidence", ""),
        }
        for field_name in field_names:
            row[field_name] = "; ".join(
                str(value) for value in examples.get(field_name, [])
            )
        rows.append(row)
    return rows


def json_to_csv(
    json_path: str | Path = DEFAULT_JSON_PATH,
    csv_path: str | Path = DEFAULT_CSV_PATH,
):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = flatten_to_rows(data)
    if not rows:
        print("No data found to write.")
        return

    fieldnames = ["document", "document_type", "type_confidence"]
    fieldnames.extend(
        field_name for field_name in rows[0] if field_name not in fieldnames
    )

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {csv_path}")


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON_PATH
    csv_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CSV_PATH
    json_to_csv(json_path, csv_path)