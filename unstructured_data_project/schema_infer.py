"""
Stage 6: field/pattern discovery — this is where TF-IDF + clustering hands
off to a simpler, more reliable tool for structured docs: regex over
"LABEL: VALUE" patterns, run separately on every document/cluster.

Stage 7: infer a type for each discovered field, then emit JSON Schema.

Why regex here and not TF-IDF? TF-IDF/clustering told us WHICH group of
lines belongs together (an "account" block, a "personal info" block, etc).
It does NOT tell us the literal key/value pairs inside that block — for
that, structured docs like this one hand you the answer directly via their
"Label: Value" formatting. This is the "NER / pattern matching" box from
the architecture diagram you pasted.
"""
import re
import json
from collections import Counter, defaultdict


LABEL_VALUE_RE = re.compile(r'([A-Z][A-Za-z0-9 /()&]{2,40}?):\s*([^:]+?)(?=\s+[A-Z][A-Za-z0-9 /()&]{2,40}:|$)')

DATE_RE = re.compile(r'^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$')
NUMBER_RE = re.compile(r'^[\d,]+(\.\d+)?$')
CURRENCY_RE = re.compile(r'^[$₹]?[\d,]+(\.\d+)?$')


def discover_fields(lines: list[dict]) -> list[dict]:
    """Scan every line for 'Label: Value' pairs. Returns raw (label, value, page) hits."""
    hits = []
    for item in lines:
        for m in LABEL_VALUE_RE.finditer(item["line"]):
            label, value = m.group(1).strip(), m.group(2).strip()
            if label and value:
                hits.append({"label": label, "value": value, "page": item["page"]})
    return hits


def normalize_label(label: str) -> str:
    """'Invoice Number' -> 'invoice_number' — canonical field name."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', label.strip().lower()).strip('_')
    return slug


def infer_type(value: str) -> str:
    v = value.strip()
    if DATE_RE.match(v):
        return "date"
    if NUMBER_RE.match(v.replace(',', '')):
        return "number"
    if v.upper() in {"TRUE", "FALSE", "YES", "NO"}:
        return "boolean"
    return "string"


def build_schema(hits: list[dict], min_occurrences: int = 1) -> dict:
    """Group hits by normalized label, keep fields that recur, infer types,
    and emit a JSON Schema (draft-07 style) plus the raw examples found."""
    grouped = defaultdict(list)
    for h in hits:
        grouped[normalize_label(h["label"])].append(h)

    properties = {}
    examples = {}
    for field_name, occurrences in grouped.items():
        if len(occurrences) < min_occurrences:
            continue
        type_votes = Counter(infer_type(o["value"]) for o in occurrences)
        inferred_type = type_votes.most_common(1)[0][0]
        properties[field_name] = {
            "type": inferred_type,
            "source_label": occurrences[0]["label"],
            "occurrences": len(occurrences),
        }
        examples[field_name] = [o["value"] for o in occurrences[:3]]

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "auto_discovered_schema",
        "type": "object",
        "properties": properties,
    }
    return schema, examples


if __name__ == "__main__":
    from extract import extract_and_clean

    lines = extract_and_clean("../sample.pdf")
    hits = discover_fields(lines)
    print(f"Discovered {len(hits)} label:value hits\n")

    schema, examples = build_schema(hits)
    print(json.dumps(schema, indent=2))
    print("\n--- example values per field ---")
    for field, vals in examples.items():
        print(f"{field}: {vals}")