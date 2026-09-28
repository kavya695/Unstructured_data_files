# Front end for the OCR pipeline

A minimal Flask web app: upload a document image in the browser, it runs
through `ocr_pipeline.pipeline.process_document()`, and the extracted
fields are shown in a clean list.

## Layout

```
app.py                  <- Flask backend (1 route for the page, 1 API route)
templates/index.html    <- upload page
static/style.css
static/script.js
ocr_pipeline/            <- your existing pipeline package (unchanged)
ocr_pipeline_uploads/    <- temp folder for uploaded files (auto-created, auto-cleaned)
```

`ocr_pipeline/` here is a straight copy of your existing package, so
`app.py` can `from ocr_pipeline.pipeline import process_document`. If you'd
rather not duplicate it, delete this copy and instead place `app.py`,
`templates/`, and `static/` directly inside your project's parent folder
(next to your existing `ocr_pipeline/` directory) so the import still works.

## Setup

```bash
# system dependency (same as the pipeline itself needs)
sudo apt-get install tesseract-ocr

# python dependencies
pip install flask opencv-python-headless pytesseract numpy scikit-learn --break-system-packages
```

(If you already had the pipeline's own `requirements.txt` installed, you
only need to add `flask`.)

## Run

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## How it works

- `GET /` serves the upload page.
- `POST /api/process` accepts a `multipart/form-data` upload (`file`, and
  optionally `doc_type` = `scanned` / `photo` / `screenshot`), saves it to a
  temp file, calls `process_document()`, deletes the temp file, and returns
  the resulting schema as JSON.
- The page's JS shows the document category, an OCR-confidence badge, a
  "needs review" badge (from `validation.needs_review`), and every non-null
  field from `result["fields"]`.

## Extending it

- **Show transactions too**: `result["transactions"]` is a list of
  `{date, description, debit, credit, balance}` dicts (present for bank
  statements) — render it as a table in `script.js`/`index.html` the same
  way `fields` is rendered.
- **Show raw OCR / debug info**: `result["_debug"]["raw_lines"]` has the
  raw OCR'd text lines; `result["image_quality"]` has the quality-check
  details. Useful behind a "show details" toggle for debugging bad
  extractions.
- **PDF support**: the pipeline itself doesn't handle multi-page PDFs yet
  (see the main README's "Known limitations"). If you want to accept PDFs
  in this UI, convert each page with `pdf2image` and call
  `process_image()` per page (see `pdf_support.py`) before wiring it into
  `/api/process`.
- **Production deployment**: the built-in `app.run()` is a dev server only.
  Run it behind `gunicorn`/`waitress` and put a real reverse proxy in front
  if you deploy this beyond your own machine.
