"""
app.py

Small Flask front end for the OCR pipeline.

Serves a single-page upload UI and one API endpoint that runs an uploaded
image through ocr_pipeline.pipeline.process_document() and returns the
resulting schema as JSON.

Setup (run from this file's folder, with the `ocr_pipeline` package copied
or symlinked in next to it -- see README_FRONTEND.md):

    pip install flask --break-system-packages
    python app.py

Then open http://127.0.0.1:5000 in a browser.
"""
import traceback
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from ocr_pipeline.pipeline import process_document
from ocr_pipeline.pdf_support import process_pdf

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "ocr_pipeline_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def api_process():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected."}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"Unsupported file type '{ext}'. "
                     f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400

    # The uploader does not need to know the capture type. The pipeline
    # classifies it when doc_type is omitted.
    doc_type = request.form.get("doc_type") or None

    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    file.save(temp_path)

    try:
        if ext == ".pdf":
            result = process_pdf(str(temp_path), doc_type=doc_type)
            result.setdefault("_debug", {})["detected_doc_type"] = result.get("source_type")
        else:
            result = process_document(str(temp_path), doc_type=doc_type)
        return jsonify(result)
    except Exception as exc:  # surface pipeline errors to the UI instead of a raw 500 page
        traceback.print_exc()
        return jsonify({"error": f"Processing failed: {exc}"}), 500
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
