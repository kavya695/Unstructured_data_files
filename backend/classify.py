"""
Stage 0 (runs alongside stage 6/7): classify WHICH KIND of document this is
(invoice, bank statement, credit report, ...) before/along with pulling out
its fields.

Fully config-driven: edit document_types.json to add a new type or tune an
existing one's keywords. No code changes needed to add a new document type.

Scoring: each matched keyword phrase in the raw text = 1 point; each
discovered field name (from schema_infer.discover_fields) that matches a
type's field_hints = 2 points, since a real structured field match is a
stronger signal than a keyword appearing once in body text. The type with
the highest score wins; if nothing scores above a small threshold, the
document is tagged 'unknown'.
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "document_types.json"


def load_type_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_document(lines: list[dict], field_names: list[str], config: dict = None) -> dict:
    """
    lines: the {'page','line'} list from extract_and_clean
    field_names: normalized field names already discovered by schema_infer
                 (e.g. ['invoice_number', 'vendor_name', ...])
    Returns {'type': str, 'confidence': float, 'scores': {type: score, ...}}
    """
    if config is None:
        config = load_type_config()

    full_text = " ".join(item["line"] for item in lines).lower()
    field_set = set(field_names)

    scores = {}
    for doc_type, sig in config.items():
        score = 0
        for kw in sig.get("keywords", []):
            if kw.lower() in full_text:
                score += 1
        for hint in sig.get("field_hints", []):
            if hint in field_set:
                score += 2
        scores[doc_type] = score

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    total = sum(scores.values()) or 1
    confidence = round(best_score / total, 2)

    if best_score == 0:
        return {"type": "unknown", "confidence": 0.0, "scores": scores}

    return {"type": best_type, "confidence": confidence, "scores": scores}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from extract import extract_and_clean
    from schema_infer import discover_fields, normalize_label

    target = sys.argv[1] if len(sys.argv) > 1 else "../sample.pdf"
    lines = extract_and_clean(target)
    hits = discover_fields(lines)
    field_names = [normalize_label(h["label"]) for h in hits]

    result = classify_document(lines, field_names)
    print(f"{target} -> {result['type']} (confidence {result['confidence']})")
    print("scores:", result["scores"])
