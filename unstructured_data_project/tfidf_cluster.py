"""
Stage 4: TF-IDF over chunks
Stage 5: cluster the resulting vectors (KMeans)

With a single sample PDF you only get chunks from ONE document, so
clustering here groups *sections within the document* rather than
*documents of different types* — but the code is identical either way.
Once you have multiple PDFs, feed all of their chunks in together and
this will group similar sections/documents across files.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np


def vectorize(chunks: list[dict]) -> tuple[np.ndarray, TfidfVectorizer]:
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9,
    )
    X = vectorizer.fit_transform(texts)
    return X, vectorizer


def cluster(X, n_clusters: int = 3) -> np.ndarray:
    n_clusters = min(n_clusters, X.shape[0])  # can't have more clusters than samples
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    return km.fit_predict(X)


def top_terms_per_cluster(X, labels, vectorizer, chunks, top_n: int = 6) -> dict:
    terms = np.array(vectorizer.get_feature_names_out())
    result = {}
    for cluster_id in sorted(set(labels)):
        idx = np.where(labels == cluster_id)[0]
        cluster_mean = X[idx].mean(axis=0).A1  # avg TF-IDF weight per term
        top_idx = cluster_mean.argsort()[::-1][:top_n]
        result[cluster_id] = {
            "top_terms": terms[top_idx].tolist(),
            "chunk_titles": [chunks[i]["title"] for i in idx],
        }
    return result


if __name__ == "__main__":
    from extract import extract_and_clean
    from chunk import chunk_by_heading

    lines = extract_and_clean("../sample.pdf")
    chunks = chunk_by_heading(lines)
    X, vectorizer = vectorize(chunks)
    labels = cluster(X, n_clusters=4)
    summary = top_terms_per_cluster(X, labels, vectorizer, chunks)

    for cid, info in summary.items():
        print(f"Cluster {cid}: top terms = {info['top_terms']}")
        for t in info["chunk_titles"]:
            print(f"    - {t}")
        print()