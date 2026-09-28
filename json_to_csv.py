"""
Stage 9: schema_output.json -> CSV

Flattens the nested JSON into one row per discovered field per document,
which is the shape that's actually useful to open in Excel/Sheets:

  document | document_type | type_confidence | field_name | field_type |
  source_label | occurrences | example_values

Usage:
    python3 json_to_csv.py                     # reads schema_output.json, writes schema_output.csv
    python3 json_to_csv.py in.json out.csv      # custom paths
"""
import sys
import json
import csv


def flatten_to_rows(data: dict) -> list[dict]:
    rows = []
    for doc_path, doc_info in data.get("schemas_by_document", {}).items():
        doc_type = doc_info.get("document_type", "unknown")
        confidence = doc_info.get("type_confidence", "")
        properties = doc_info.get("schema", {}).get("properties", {})
        examples = doc_info.get("examples", {})

        if not properties:
            # still emit one row so the document isn't silently dropped from the CSV
            rows.append({
                "document": doc_path,
                "document_type": doc_type,
                "type_confidence": confidence,
                "field_name": "",
                "field_type": "",
                "source_label": "",
                "occurrences": "",
                "example_values": "",
            })
            continue

        for field_name, field_info in properties.items():
            rows.append({
                "document": doc_path,
                "document_type": doc_type,
                "type_confidence": confidence,
                "field_name": field_name,
                "field_type": field_info.get("type", ""),
                "source_label": field_info.get("source_label", ""),
                "occurrences": field_info.get("occurrences", ""),
                "example_values": "; ".join(str(v) for v in examples.get(field_name, [])),
            })
    return rows


def json_to_csv(json_path: str = "schema_output.json", csv_path: str = "schema_output.csv"):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = flatten_to_rows(data)
    if not rows:
        print("No data found to write.")
        return

    fieldnames = ["document", "document_type", "type_confidence", "field_name",
                  "field_type", "source_label", "occurrences", "example_values"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {csv_path}")


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "schema_output.json"
    csv_path = sys.argv[2] if len(sys.argv) > 2 else "schema_output.csv"
    json_to_csv(json_path, csv_path)