"""JSON API for processing files in the backend input directory."""
import json
import os
import re
import shutil
import stat
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from main import HISTORY_DIR, OUTPUT_DIR, process_input_files


JSON_OUTPUT_PATH = OUTPUT_DIR / "schema_output.json"
CSV_OUTPUT_PATH = OUTPUT_DIR / "schema_output.csv"
HISTORY_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
API_ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get("API_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}

app = Flask(__name__, static_folder=None)


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    return jsonify({"error": error.description}), error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    if isinstance(error, HTTPException):
        return handle_http_error(error)
    app.logger.exception("Unhandled API error", exc_info=error)
    return jsonify({"error": "Internal server error."}), 500


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in API_ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.vary.add("Origin")
    return response


def history_entry_path(history_id: str) -> Path:
    if not HISTORY_ID_PATTERN.fullmatch(history_id):
        abort(404)
    path = (HISTORY_DIR / history_id).resolve()
    if path.parent != HISTORY_DIR.resolve() or not path.is_dir():
        abort(404)
    return path


def read_history() -> list[dict]:
    entries = []
    if not HISTORY_DIR.is_dir():
        return entries

    for entry_path in HISTORY_DIR.iterdir():
        if not entry_path.is_dir():
            continue
        try:
            metadata = json.loads(
                (entry_path / "metadata.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue
        try:
            output = json.loads(
                (entry_path / "output.json").read_text(encoding="utf-8")
            )
            metadata["documents"] = output.get("documents_processed", [])
        except (OSError, json.JSONDecodeError):
            metadata["documents"] = metadata.get("original_filenames", [])
        entries.append(metadata)
    return sorted(
        entries,
        key=lambda item: item.get("processed_at", item.get("uploaded_at", "")),
        reverse=True,
    )


def clear_history_storage() -> int:
    if not HISTORY_DIR.is_dir():
        return 0

    removed = 0
    for entry_path in HISTORY_DIR.iterdir():
        if entry_path.is_dir():
            for child_path in [entry_path, *entry_path.rglob("*")]:
                try:
                    os.chmod(child_path, stat.S_IREAD | stat.S_IWRITE)
                except OSError:
                    pass
            shutil.rmtree(entry_path)
            removed += 1
        elif entry_path.is_file():
            entry_path.unlink()
    return removed


@app.post("/api/process")
def process_input():
    try:
        result, history_id = process_input_files()
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"history_id": history_id, "processing_result": result}), 201


@app.get("/api/current")
def get_current():
    if not JSON_OUTPUT_PATH.is_file():
        abort(404, description="Current output is not available.")
    return send_file(JSON_OUTPUT_PATH, mimetype="application/json")


@app.get("/api/current/csv")
def download_current_csv():
    if not CSV_OUTPUT_PATH.is_file():
        abort(404, description="Current CSV is not available.")
    return send_file(CSV_OUTPUT_PATH, as_attachment=True, download_name="schema_output.csv")


@app.get("/api/current/json")
def download_current_json():
    if not JSON_OUTPUT_PATH.is_file():
        abort(404, description="Current JSON is not available.")
    return send_file(JSON_OUTPUT_PATH, as_attachment=True, download_name="schema_output.json")


@app.get("/api/history")
def get_history():
    return jsonify({"history": read_history()})


@app.get("/api/history/<history_id>")
def get_history_entry(history_id: str):
    entry_path = history_entry_path(history_id)
    metadata = json.loads(
        (entry_path / "metadata.json").read_text(encoding="utf-8")
    )
    output_path = entry_path / "output.json"
    if output_path.is_file():
        metadata["processing_result"] = json.loads(
            output_path.read_text(encoding="utf-8")
        )
    return jsonify({"history": metadata})


@app.get("/api/history/<history_id>/csv")
def download_history_csv(history_id: str):
    csv_path = history_entry_path(history_id) / "output.csv"
    if not csv_path.is_file():
        abort(404, description="Historical CSV is not available.")
    return send_file(csv_path, as_attachment=True, download_name=f"{history_id}.csv")


@app.get("/api/history/<history_id>/json")
def download_history_json(history_id: str):
    json_path = history_entry_path(history_id) / "output.json"
    if not json_path.is_file():
        abort(404, description="Historical JSON is not available.")
    return send_file(json_path, as_attachment=True, download_name=f"{history_id}.json")


@app.post("/api/history/clear")
def clear_history():
    return jsonify({"entries_cleared": clear_history_storage()})


if __name__ == "__main__":
    app.run(debug=True)
