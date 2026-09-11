"""
Full pipeline: PDF(s) -> text -> clean -> chunk -> TF-IDF -> cluster ->
field discovery -> JSON Schema.

Usage:
    python3 main.py file1.pdf file2.pdf ...
    python3 main.py *.pdf

With ONE pdf, clustering groups sections *within* that document.
With MULTIPLE pdfs of different types (invoices, medical records, etc.),
clustering groups documents/sections *across* files — that's when TF-IDF +
KMeans genuinely earns its keep, per the architecture you were sketching out.
"""
import sys
import json
import glob

from extract import extract_and_clean
from chunk import chunk_by_heading
from tfidf_cluster import vectorize, cluster, top_terms_per_cluster
from schema_infer import discover_fields, build_schema, normalize_label
from classify import classify_document, load_type_config


def run_pipeline(pdf_paths: list[str], n_clusters: int = 3, out_path: str = "schema_output.json"):
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

    result = {
        "documents_processed": pdf_paths,
        "clusters": {
            str(cid): {"top_terms": info["top_terms"], "chunks": info["chunk_titles"]}
            for cid, info in cluster_summary.items()
        },
        "schemas_by_document": schemas,
    }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDone. Full output written to {out_path}")
    return result


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        paths = glob.glob("../*.pdf")
    if not paths:
        print("Usage: python3 main.py file1.pdf [file2.pdf ...]")
        sys.exit(1)
    run_pipeline(paths)