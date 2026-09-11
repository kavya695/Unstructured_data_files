# Multi-format -> TF-IDF -> Clustering -> Schema pipeline

Handles **PDF, Word (.docx), and Email (.eml / .msg)** as input, all
normalized to the same internal shape so chunking/TF-IDF/clustering/schema
inference is 100% shared code regardless of source format.

## Setup
```
pip install -r requirements.txt --break-system-packages
```
Also needs the `tesseract` OCR binary on the system PATH (used only when a
PDF page has no text layer, i.e. it's scanned):
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Mac: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

## Run
```
python3 main.py file1.pdf file2.docx file3.eml ...
```
Mix and match any supported formats in one call — they get pooled together
for clustering. Output goes to `schema_output.json`.

## Supported formats
| Extension | How it's read | Extra dependency |
|---|---|---|
| `.pdf` | PyMuPDF text layer, OCR fallback for scanned pages | `pymupdf`, `pytesseract` (+ tesseract binary) |
| `.docx` | python-docx: paragraphs + tables (tables kept separate from prose) | `python-docx` |
| `.eml` | stdlib `email` module — headers become Label:Value lines automatically | none |
| `.msg` | Outlook binary format | `extract-msg` |
| `.txt` | read as-is | none |

**Not supported directly:** old binary `.doc`. Convert first, e.g.:
`libreoffice --headless --convert-to docx yourfile.doc`

## Adding a new format
1. Write a function in `extractors/your_format.py` that takes a path and
   returns `list[str]` (one string per "page"/section).
2. Register the extension in `EXTRACTORS` at the top of `extract.py`.
   Nothing else changes — chunking, TF-IDF, clustering, and schema
   inference all operate on the same normalized `{page, line}` shape.

## Document type classification (NEW)
Every document is now also tagged with a `document_type` (invoice, purchase_order,
bank_statement, credit_report, medical_record, resume, contract, or `unknown`),
plus a confidence score, in `schema_output.json`.

This is fully **config-driven** — edit `document_types.json` to add a new type
or tune keywords for an existing one. No code changes needed:
```json
"bank_statement": {
  "keywords": ["account statement", "opening balance", "closing balance", "ifsc"],
  "field_hints": ["account_number", "opening_balance", "closing_balance"]
}
```
`keywords` are phrases matched anywhere in the document's raw text (1 point each).
`field_hints` are normalized field names that schema_infer.py already discovered
via Label:Value pattern matching (2 points each, since a real structured field
match is a stronger signal than a keyword appearing once in a sentence). Highest
score wins; ties/no-match fall back to `unknown`.

Tested on your CIBIL PDF, the sample purchase order docx, and the sample
invoice eml — all three classified correctly with clear confidence separation
(credit_report 0.80, purchase_order 0.85, invoice 0.69).

## Files
- `extract.py` – Stage 1-2: dispatches to the right extractor by file extension, then cleans lines
- `extractors/pdf_extractor.py` – PDF text + OCR fallback
- `extractors/docx_extractor.py` – Word paragraphs + tables
- `extractors/email_extractor.py` – .eml (stdlib) and .msg (extract-msg) parsing, headers + body + attachment names
- `chunk.py` – Stage 3: split lines into sections by heading detection
- `tfidf_cluster.py` – Stage 4-5: TF-IDF vectorize chunks, KMeans cluster
- `schema_infer.py` – Stage 6-7: regex-based "Label: Value" field discovery, type inference, JSON Schema generation
- `classify.py` – Stage 8: document-type classification (invoice / bank statement / etc.), config-driven via `document_types.json`
- `document_types.json` – editable list of document types and their keyword/field signatures
- `main.py` – ties it all together

## Notes
- Tested end-to-end on a scanned CIBIL credit report (PDF, OCR path), a
  synthetic purchase order (.docx, paragraphs + table), and a synthetic
  invoice email (.eml, headers + body) — all three produced correct,
  distinct schemas in one run of `main.py`.
- Email headers (Subject/From/To/Date) are emitted as literal
  "Label: Value" lines, so they fall straight into the same field-discovery
  regex as everything else — no special-casing needed.
- With more documents, clustering starts grouping similar document *types*
  together across formats (e.g. all your invoices, regardless of whether
  they arrived as PDF or email, land in the same cluster) rather than just
  sections within one file.
