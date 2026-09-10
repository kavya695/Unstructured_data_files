"""
normalize.py

Converts raw extracted strings into typed, cleaned values matching a
fixed output schema. This is the step that makes downstream code
(DB inserts, business rules, comparisons) not have to deal with
"Rs. 2,45,000" vs "245000.0" vs "INR 245000".
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d"]
# Matches the numeric portion of an amount, tolerating Indian-style lakh/crore
# grouping (e.g. "5,00,000") as well as standard grouping (e.g. "500,000").
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalize_currency(raw: Optional[str]) -> Optional[float]:
    """'Rs. 5,00,000' / 'INR 12,450.50' / '₹2,45,000' -> float.
    Deliberately ignores currency symbols/letters (Rs, INR, ₹, $) rather than
    stripping non-digits blindly, since a literal '.' in 'Rs.' would otherwise
    get treated as a decimal point."""
    if not raw:
        return None
    m = NUMBER_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(0).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None  # leave as null if unparseable rather than guessing


def normalize_account_number(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", raw).upper()
    return cleaned.rstrip(".,:;")


def normalize_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    return int(m.group(0)) if m else None


# Schema: canonical_key -> normalizer function
SCHEMA_NORMALIZERS = {
    "account_number": normalize_account_number,
    "account_type": lambda v: v.strip().title() if v else None,
    "lender": lambda v: v.strip() if v else None,
    "date_opened": normalize_date,
    "sanctioned_amount": normalize_currency,
    "current_balance": normalize_currency,
    "emi_amount": normalize_currency,
    "payment_status": lambda v: v.strip().title() if v else None,
    "days_past_due": normalize_int,
    "last_payment_date": normalize_date,
    "credit_score": normalize_int,
    # invoice fields
    "invoice_number": lambda v: v.strip() if v else None,
    "invoice_date": normalize_date,
    "due_date": normalize_date,
    "bill_to": lambda v: v.strip() if v else None,
    "subtotal": normalize_currency,
    "tax_amount": normalize_currency,
    "total_amount": normalize_currency,
    # bank statement fields
    "account_holder": lambda v: v.strip().title() if v else None,
    "statement_period": lambda v: v.strip() if v else None,
    "opening_balance": normalize_currency,
    "closing_balance": normalize_currency,
}

# Which fields are "must-have" depends on the document category - a bank
# statement will never have an "emi_amount", so don't flag it as missing.
REQUIRED_FIELDS_BY_CATEGORY = {
    "credit_report": ["account_number", "current_balance", "payment_status"],
    "invoice": ["invoice_number", "total_amount"],
    "bank_statement": ["account_number", "closing_balance"],
    "unknown": ["account_number"],  # best-effort guess when category is unknown
}


def normalize_fields(raw_fields: Dict[str, str]) -> Dict[str, Any]:
    result = {}
    for key, normalizer in SCHEMA_NORMALIZERS.items():
        result[key] = normalizer(raw_fields.get(key))
    return result


def normalize_transaction_row(row: Dict[str, str]) -> Dict[str, Any]:
    return {
        "date": normalize_date(row.get("date")),
        "description": (row.get("description") or "").strip() or None,
        "debit": normalize_currency(row.get("debit")) if row.get("debit") not in (None, "-", "") else None,
        "credit": normalize_currency(row.get("credit")) if row.get("credit") not in (None, "-", "") else None,
        "balance": normalize_currency(row.get("balance")),
    }


def build_schema(extraction: Dict, doc_type: str, avg_confidence: float,
                  document_category: Dict = None) -> Dict[str, Any]:
    fields = normalize_fields(extraction.get("fields", {}))
    transactions = [normalize_transaction_row(r) for r in extraction.get("transactions", [])]

    category = (document_category or {}).get("category", "unknown")
    required = REQUIRED_FIELDS_BY_CATEGORY.get(category, REQUIRED_FIELDS_BY_CATEGORY["unknown"])
    missing = [f for f in required if fields.get(f) is None]

    return {
        "source_type": doc_type,
        "document_category": document_category or {"category": "unknown", "method": "none", "confidence": 0.0},
        "ocr_confidence": round(avg_confidence, 1),
        "fields": fields,
        "transactions": transactions,
        "validation": {
            "missing_required_fields": missing,
            "needs_review": bool(missing) or avg_confidence < 60.0,
        },
    }
