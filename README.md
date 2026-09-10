# OCR Document Extraction Pipeline

Turns an image (scanned page, phone photo, or app screenshot) of a financial
document into structured, typed JSON:

```
Image -> preprocess (per input type) -> OCR (text + coordinates)
       -> document-type classification -> field/table extraction
       -> normalization -> schema
```

## Install

```bash
sudo apt-get install tesseract-ocr        # system binary (Linux)
pip install pytesseract opencv-python numpy --break-system-packages
```

## Use

```python
from ocr_pipeline.pipeline import process_document

result = process_document("statement.png", doc_type="scanned")  # or "photo" / "screenshot"
print(result["fields"]["current_balance"])   # 245000.0 (float, ready to use)
print(result["validation"]["needs_review"])  # True if confidence is low or required fields are missing
```

Or from the command line:

```bash
python3 -m ocr_pipeline.pipeline statement.png scanned
python3 -m ocr_pipeline.run_samples   # runs all 3 bundled samples
```

If you don't know the input type ahead of time, omit `doc_type` and
`classify_doc_type()` will guess from image statistics (rough heuristic —
better to have your upload UI tell you the type directly if you can).

## Files

| File | Responsibility |
|---|---|
| `preprocess.py` | Per-type image cleanup: deskew, perspective-correct, denoise, lighting normalization |
| `ocr.py` | Runs Tesseract, returns word-level text + bounding boxes, groups into lines |
| `classify.py` | Identifies the document *type* (invoice / bank statement / credit report) from its OCR'd text, via keyword rules first, trained TF-IDF model as fallback |
| `train_classifier.py` | Builds a synthetic labeled corpus and trains the TF-IDF classifier used by `classify.py` |
| `extract.py` | Finds `label: value` pairs, grid/card layouts, and transaction tables |
| `normalize.py` | Types and cleans raw strings into a fixed schema (currency → float, dates → ISO, etc.); picks required fields based on document category |
| `pipeline.py` | Wires the above together; `process_document()` is the main entry point |

## Document type classification

Before field extraction runs, `classify_document()` (in `classify.py`) figures
out *what kind* of document this is, using two strategies in order:

1. **Keyword rules** (`KEYWORD_RULES` dict) — instant, no training needed.
   Checks the OCR'd text for distinctive phrases per category (e.g. "tax
   invoice", "opening balance", "credit account details"). This is the
   default and works as long as your real documents use similar wording.
2. **TF-IDF + Logistic Regression** (`DocumentTypeClassifier`) — only used
   as a fallback when keyword rules aren't confident. Needs a trained model
   file (`classifier_model.pkl`, already included, trained on synthetic
   data — see below). Handles wording variation the keyword list doesn't
   cover, at the cost of needing labeled training examples.

Retrain on your own labeled data once you have some:

```python
from train_classifier import train_from_csv
train_from_csv("my_labeled_documents.csv")  # columns: text,label
```

The output schema now includes:
```json
"document_category": {
  "category": "invoice",
  "method": "keyword_rules",
  "confidence": 1.0,
  "matched_phrases": ["tax invoice", "invoice number", "bill to"]
}
```
Which required fields get checked for `needs_review` also depends on this —
see `REQUIRED_FIELDS_BY_CATEGORY` in `normalize.py` (a bank statement isn't
penalized for missing an `emi_amount`, etc.).

## Extending to your own fields

Everything field-specific lives in two places:

1. **`extract.py` → `LABEL_ALIASES`**: map any label spelling/OCR variant you
   see to a canonical key, e.g. `"outstanding amt": "current_balance"`.
2. **`normalize.py` → `SCHEMA_NORMALIZERS`**: add the canonical key with a
   function that converts the raw string to its final type.

Both the colon-based extractor (`"Label: Value"`) and the grid extractor
(labels in one row, values in the row below — common in dashboard
screenshots) key off the same `LABEL_ALIASES` map, so one addition covers
both layouts.

## Known limitations (things to improve before production)

- `classify_doc_type()` (input format: scanned/photo/screenshot) is a rough
  brightness/saturation heuristic, not a trained classifier — fine for a
  demo, not for real traffic. Better to have the upload flow tell you the
  type, or train a small image classifier. (This is separate from document
  *category* classification below — one asks "how was this captured," the
  other asks "what kind of document is it.")
- Document category classification's keyword rules were written by hand for
  3 categories with fairly distinctive vocabularies — add your own phrases to
  `KEYWORD_RULES` in `classify.py` for new categories, or retrain the TF-IDF
  model on real labeled examples once you have them (synthetic training
  text only teaches the model vocabulary someone thought to generate).
- `classify_by_keywords()` uses hit-counting, not a calibrated probability —
  treat `confidence` as "how many distinctive phrases matched," not a true
  statistical confidence.
- The transaction-table parser assumes a `Date | Description | Debit |
  Credit | Balance` shape with clear column gaps. Real bank statements vary
  a lot — you'll likely want per-bank table templates for production. It
  can also mistake a trailing footer line for an extra (garbage) row if the
  footer happens to contain digits — worth a stricter "stop" condition if
  this shows up on real statements.
- No support yet for multi-page PDFs — `pdf2image` can convert each page to
  a PNG first, then feed each page through `process_document()` individually.
- Field values pulled from a status *badge* rather than the label grid (e.g.
  "Status: Current" floating outside the label row) aren't picked up —
  visible in the bundled screenshot sample, correctly flagged via
  `needs_review`.
