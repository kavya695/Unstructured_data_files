"""
Full pipeline: PDF(s)/Word/Email -> text -> clean -> chunk -> TF-IDF ->
cluster -> field discovery -> classify -> JSON Schema.

Usage:
    python3 main.py file1.pdf file2.docx file3.eml    # process specific files
    python3 main.py                                    # "run all": auto-discovers
                                                         # every supported file
                                                         # sitting directly in
                                                         # backend/input/

With ONE document, clustering groups sections *within* that document.
With MULTIPLE documents of different types (invoices, medical records, etc.),
clustering groups documents/sections *across* files — that's when TF-IDF +
KMeans genuinely earns its keep, per the architecture you were sketching out.
"""
import sys
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from extract import extract_and_clean, EXTRACTORS
from chunk import chunk_by_heading
from tfidf_cluster import vectorize, cluster, top_terms_per_cluster
from schema_infer import discover_fields, build_schema, normalize_label
from classify import classify_document, load_type_config
from json_to_csv import json_to_csv


BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_DIR = BASE_DIR / "history"
DEFAULT_JSON_OUTPUT_PATH = OUTPUT_DIR / "schema_output.json"


def ensure_pipeline_directories() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def discover_documents(folder: str | Path = INPUT_DIR) -> list[str]:
    """Find supported input files directly inside the input folder."""
    ensure_pipeline_directories()
    found = []
    for path in sorted(Path(folder).iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() in EXTRACTORS:
            found.append(str(path))
    return found


def run_pipeline(
    pdf_paths: list[str],
    n_clusters: int = 3,
    out_path: str | None = None,
    document_labels: dict[str, str] | None = None,
):
    """Run the pipeline and write JSON plus a sibling CSV file.

    ``document_labels`` lets callers preserve source filenames when processing
    files from the input folder.
    """
    ensure_pipeline_directories()
    out_path = out_path or str(DEFAULT_JSON_OUTPUT_PATH)
    all_lines = []       # for field discovery (per-doc)
    all_chunks = []       # for TF-IDF/clustering (across all docs)
    per_doc_hits = {}
    per_doc_lines = {}
    type_config = load_type_config()

    for path in pdf_paths:
        print(f"[1-2] Extracting + cleaning: {path}")
        lines = extract_and_clean(path)
        all_lines.extend(lines)
        per_doc_lines[path] = lines

        print(f"[3]   Chunking into sections")
        chunks = chunk_by_heading(lines)
        for c in chunks:
            c["source_pdf"] = path
        all_chunks.extend(chunks)

        print(f"[6]   Discovering label:value fields")
        per_doc_hits[path] = discover_fields(lines)

    print(f"\n[4]   TF-IDF over {len(all_chunks)} chunks from {len(pdf_paths)} document(s)")
    X, vectorizer = vectorize(all_chunks)

    print(f"[5]   Clustering into up to {n_clusters} groups")
    labels = cluster(X, n_clusters=n_clusters)
    cluster_summary = top_terms_per_cluster(X, labels, vectorizer, all_chunks)

    print(f"[7]   Inferring schema per document")
    print(f"[8]   Classifying document type per document")
    schemas = {}
    for path, hits in per_doc_hits.items():
        schema, examples = build_schema(hits)
        field_names = [normalize_label(h["label"]) for h in hits]
        doc_type = classify_document(per_doc_lines[path], field_names, type_config)
        schemas[path] = {
            "document_type": doc_type["type"],
            "type_confidence": doc_type["confidence"],
            "type_scores": doc_type["scores"],
            "schema": schema,
            "examples": examples,
        }

    labels = document_labels or {}
    result = {
        "documents_processed": [labels.get(path, path) for path in pdf_paths],
        "clusters": {
            str(cid): {"top_terms": info["top_terms"], "chunks": info["chunk_titles"]}
            for cid, info in cluster_summary.items()
        },
        "schemas_by_document": {
            labels.get(path, path): info for path, info in schemas.items()
        },
    }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDone. Full output written to {out_path}")

    csv_path = out_path.rsplit(".", 1)[0] + ".csv"
    json_to_csv(out_path, csv_path)

    print("\n--- Document type summary ---")
    for path, info in schemas.items():
        field_count = len(info["schema"]["properties"])
        print(f"  {path}: {info['document_type']} "
              f"(confidence {info['type_confidence']}, {field_count} fields found)")

    return result


def process_files(paths: list[str]) -> tuple[dict, str]:
    """Process one input batch and archive its successful result separately."""
    labels = {path: Path(path).name for path in paths}
    result = run_pipeline(paths, document_labels=labels)

    history_id = uuid.uuid4().hex
    entry_path = HISTORY_DIR / history_id
    entry_path.mkdir(parents=True)
    document_types = sorted({
        info.get("document_type", "unknown")
        for info in result.get("schemas_by_document", {}).values()
    })
    metadata = {
        "id": history_id,
        "original_filenames": result.get("documents_processed", []),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "document_types": document_types,
    }
    shutil.copyfile(DEFAULT_JSON_OUTPUT_PATH, entry_path / "output.json")
    shutil.copyfile(OUTPUT_DIR / "schema_output.csv", entry_path / "output.csv")
    (entry_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return result, history_id


def process_input_files() -> tuple[dict, str]:
    """Process the supported files currently present in ``backend/input``."""
    paths = discover_documents()
    if not paths:
        raise FileNotFoundError(f"No supported documents found in {INPUT_DIR}.")
    return process_files(paths)


if __name__ == "__main__":
    ensure_pipeline_directories()
    paths = sys.argv[1:]
    if not paths:
        paths = discover_documents()
        if paths:
            print(f"No files given on the command line — auto-discovered {len(paths)} "
                f"supported file(s) in {INPUT_DIR}:")
            for p in paths:
                print(f"    {p}")
            print()
    if not paths:
        print("No supported files found. Either:")
        print(f"  - drop PDF/.docx/.eml/.msg/.txt files into {INPUT_DIR} and run:")
        print("        python3 main.py")
        print("  - or name specific files:")
        print("        python3 main.py file1.pdf file2.docx file3.eml")
        sys.exit(1)
    result, history_id = process_files(paths)
    print(f"Saved processing history: {history_id}")