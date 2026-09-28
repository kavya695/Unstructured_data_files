"""
extract.py

Turns OCR'd lines into structured fields:
    "Account Number: XXXXXXXX4821"  ->  {"account_number": "XXXXXXXX4821"}

Two extraction strategies, used together:
    1. Label/value pairs - lines matching "Label: Value" or "Label   Value"
       (label on the left, value on the right, common in scanned reports
       and screenshots with a two-column layout).
    2. Known-field regex fallback - scans full page text for patterns like
       account numbers, currency amounts, dates, in case the label/value
       split above didn't catch them (e.g. noisy OCR broke the ":" apart).

Then normalize.py cleans/types the raw strings into a consistent schema.
"""

import re
from typing import List, Dict, Optional
from .ocr import Line

# Canonical field names we care about for this project (credit/loan docs).
# Map various label spellings/OCR noise variants -> canonical key.
LABEL_ALIASES = {
    "account number": "account_number",
    "account no": "account_number",
    "a/c number": "account_number",
    "account type": "account_type",
    "lender": "lender",
    "date opened": "date_opened",
    "sanctioned amount": "sanctioned_amount",
    "loan amount": "sanctioned_amount",
    "current balance": "current_balance",
    "balance": "current_balance",
    "emi amount": "emi_amount",
    "emi": "emi_amount",
    "payment status": "payment_status",
    "status": "payment_status",
    "days past due": "days_past_due",
    "dpd": "days_past_due",
    "last payment date": "last_payment_date",
    "credit score": "credit_score",
    # invoice fields
    "invoice number": "invoice_number",
    "invoice no": "invoice_number",
    "invoice date": "invoice_date",
    "due date": "due_date",
    "bill to": "bill_to",
    "subtotal": "subtotal",
    "tax": "tax_amount",
    "total": "total_amount",
    # bank statement fields
    "account holder": "account_holder",
    "statement period": "statement_period",
    "opening balance": "opening_balance",
    "closing balance": "closing_balance",
}

LABEL_VALUE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z /]{2,40}?)\s*[:\-]\s*(.+)$")

# Sorted longest-first so "date opened" is tried before a shorter alias like
# "date" would ever get a chance to shadow it.
_SORTED_ALIASES = sorted(LABEL_ALIASES.keys(), key=len, reverse=True)

# Fallback regexes: only for fields where a generic pattern is unambiguous
# enough to search the *whole page* safely. Deliberately excludes anything
# like credit_score/date_opened, where a bare number/date elsewhere on the
# page (e.g. inside a table) would produce a false match - those rely on
# label/value or table detection instead.
FALLBACK_PATTERNS = {
    "account_number": re.compile(r"\b([X\*]{4,}\d{3,6}|\d{9,18})\b"),
}


def normalize_label(label: str) -> Optional[str]:
    key = re.sub(r"\s+", " ", label.strip().lower()).rstrip(":")
    return LABEL_ALIASES.get(key)


def extract_label_value_pairs(lines: List[Line]) -> Dict[str, str]:
    """
    Two passes per line:
      1. Strict "Label: Value" / "Label - Value" match.
      2. Prefix match against known label phrases, for cases where OCR
         merged the label and value with just whitespace and no punctuation
         (common when a colon renders faintly and tesseract drops it),
         e.g. "Credit Score 742 (Good)" -> label "credit score", value "742 (Good)".
    """
    fields = {}
    for line in lines:
        text = line.text.strip()

        m = LABEL_VALUE_RE.match(text)
        if m:
            canon = normalize_label(m.group(1))
            value = m.group(2).strip()
            if canon and value:
                fields.setdefault(canon, value)
                continue

        # If this line itself contains 2+ known label phrases (a grid header
        # row, e.g. "ACCOUNT NUMBER ACCOUNT TYPE LENDER"), it's not a
        # "label value" line - leave it for extract_grid_pairs to handle
        # against the row below instead of grabbing the next label as a value.
        if len(find_label_spans(line)) >= 2:
            continue

        low = text.lower()
        for alias in _SORTED_ALIASES:
            if low.startswith(alias):
                rest = text[len(alias):].strip(" :-")
                if rest:
                    fields.setdefault(LABEL_ALIASES[alias], rest)
                break
    return fields


def find_label_spans(line: Line):
    """
    Detects known multi-word label phrases within a single OCR line by
    matching consecutive word tokens (e.g. words ["ACCOUNT","NUMBER"] ->
    "account number"), and returns each match's canonical key plus its
    pixel x-range - used to line labels up with values sitting directly
    below them in a card/grid layout (as opposed to a "Label: Value" list).
    """
    words = line.words
    used = [False] * len(words)
    spans = []
    for alias in _SORTED_ALIASES:
        tokens = alias.split()
        n = len(tokens)
        for start in range(len(words) - n + 1):
            if any(used[start:start + n]):
                continue
            candidate = [words[start + k].text.lower().strip(":") for k in range(n)]
            if candidate == tokens:
                x0 = words[start].x
                x1 = words[start + n - 1].x + words[start + n - 1].w
                spans.append((LABEL_ALIASES[alias], x0, x1))
                for k in range(n):
                    used[start + k] = True
    spans.sort(key=lambda s: s[1])
    return spans


def extract_grid_pairs(lines: List[Line]) -> Dict[str, str]:
    """
    Handles dashboard/card-style layouts where several labels sit in one row
    and their values sit in the row directly beneath, column-aligned by
    x-position rather than joined with a colon - e.g.:

        ACCOUNT NUMBER   ACCOUNT TYPE     LENDER
        XXXXXXXX4821     Personal Loan    Horizon Finance Bank

    Only fires on rows containing 2+ recognized label phrases, to avoid
    misreading ordinary prose as a grid.
    """
    fields = {}
    for i in range(len(lines) - 1):
        spans = find_label_spans(lines[i])
        if len(spans) < 2:
            continue
        value_line = lines[i + 1]
        for idx, (canon, x0, _x1) in enumerate(spans):
            next_x0 = spans[idx + 1][1] if idx + 1 < len(spans) else float("inf")
            # small left margin so a value starting slightly left of its label
            # (common with right-shifted numerals) still gets captured
            val_words = [w.text for w in value_line.words if x0 - 25 <= w.x < next_x0 - 25]
            if val_words:
                fields.setdefault(canon, " ".join(val_words))
    return fields


def extract_fallback_fields(full_text: str, already_found: Dict[str, str]) -> Dict[str, str]:
    fields = {}
    for key, pattern in FALLBACK_PATTERNS.items():
        if key in already_found:
            continue
        m = pattern.search(full_text)
        if m:
            fields[key] = m.group(0).strip()
    return fields


TABLE_HEADER_KEYWORDS = {"date", "description", "debit", "credit", "balance"}


def extract_transaction_table(lines: List[Line]) -> List[Dict[str, str]]:
    """
    Detects a simple bank-statement-style table by finding a header line
    containing several known column keywords, then reading subsequent
    lines as rows, splitting on runs of 2+ spaces (OCR usually preserves
    column gaps as extra whitespace) or a minimum column count of words.
    """
    header_idx = None
    for i, line in enumerate(lines):
        words_lower = {w.lower().strip(",:") for w in line.text.split()}
        if len(words_lower & TABLE_HEADER_KEYWORDS) >= 3:
            header_idx = i
            break
    if header_idx is None:
        return []

    header_cols = [w.lower() for w in lines[header_idx].text.split() if w]
    rows = []
    for line in lines[header_idx + 1:]:
        # Stop the table at the first line that looks like prose/footer
        if re.search(r"[a-zA-Z]{4,}.*[a-zA-Z]{4,}.*[a-zA-Z]{4,}", line.text) and not re.search(r"\d", line.text):
            break
        parts = re.split(r"\s{2,}", line.text.strip())
        if len(parts) < 3:
            parts = line.text.split()
        if not parts or not re.search(r"\d", line.text):
            continue
        row = {"raw": line.text}
        # naive positional mapping: date, description, debit, credit, balance
        labels = ["date", "description", "debit", "credit", "balance"]
        # last two/three tokens are usually numeric columns; treat the rest as description
        numeric_tail = [p for p in parts if re.search(r"\d", p)]
        text_head = [p for p in parts if p not in numeric_tail]
        if parts:
            row["date"] = parts[0] if re.search(r"\d{1,2}[/\-]\d{1,2}", parts[0]) else ""
        row["description"] = " ".join(parts[1:-3]) if len(parts) > 4 else " ".join(text_head)
        tail = parts[-3:] if len(parts) >= 3 else parts
        for label, val in zip(["debit", "credit", "balance"], tail[-3:]):
            row[label] = val
        rows.append(row)
    return rows


def extract_fields(lines: List[Line]) -> Dict:
    full_text = "\n".join(l.text for l in lines)
    fields = extract_label_value_pairs(lines)
    for key, value in extract_grid_pairs(lines).items():
        fields.setdefault(key, value)
    for key, value in extract_fallback_fields(full_text, fields).items():
        fields.setdefault(key, value)
    table = extract_transaction_table(lines)
    return {"fields": fields, "transactions": table}
