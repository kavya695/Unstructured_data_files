"""
classify.py

Answers a *different* question than extract.py: not "what is the balance"
but "what kind of document is this at all" - invoice vs. bank statement
vs. credit report vs. something else. Runs on the full OCR'd text of a page,
right after OCR and before field extraction.

Two strategies, tried in order:

    1. Keyword rules (classify_by_keywords) - instant, no training data,
       works as soon as you write down a few distinctive phrases per
       category. This is the right default until it starts failing on
       real documents.

    2. TF-IDF + Logistic Regression (DocumentTypeClassifier) - needs
       labeled example documents to train on, but generalizes better to
       wording the keyword list doesn't cover. Only used as a fallback
       when keyword rules aren't confident, and only if a trained model
       file is present - this module works fine with zero ML dependency
       if you never train one.
"""

import re
import pickle
from pathlib import Path
from typing import Optional, List, Tuple, Dict


# ---------------------------------------------------------------------------
# Strategy 1: keyword rules
# ---------------------------------------------------------------------------

# Each phrase should be distinctive enough that seeing it is strong evidence
# of the category - avoid generic words ("amount", "date") that show up
# everywhere regardless of document type.
KEYWORD_RULES: Dict[str, List[str]] = {
    "invoice": [
        "tax invoice", "invoice number", "invoice date", "bill to",
        "subtotal", "unit price", "ship to", "due date",
    ],
    "bank_statement": [
        "account statement", "opening balance", "closing balance",
        "transaction history", "ifsc", "statement period", "average balance",
    ],
    "credit_report": [
        "credit account details", "consumer credit information",
        "payment status", "days past due", "sanctioned amount",
        "credit score",
    ],
}

MIN_KEYWORD_HITS = 1  # how many distinct phrases must match to call it confident


def classify_by_keywords(text: str) -> Tuple[str, float, List[str]]:
    """
    Returns (category, confidence, matched_phrases).
    confidence here is just "number of distinct matched phrases" normalized
    to a 0-1-ish scale - it's a hit count, not a calibrated probability.
    Returns ("unknown", 0.0, []) if nothing matched.
    """
    low = text.lower()
    scores = {}
    matches = {}
    for category, phrases in KEYWORD_RULES.items():
        hits = [p for p in phrases if p in low]
        if hits:
            scores[category] = len(hits)
            matches[category] = hits

    if not scores:
        return "unknown", 0.0, []

    best_category = max(scores, key=scores.get)
    if scores[best_category] < MIN_KEYWORD_HITS:
        return "unknown", 0.0, []

    # crude confidence: matched phrases / total phrases defined for that category
    confidence = min(1.0, scores[best_category] / max(2, len(KEYWORD_RULES[best_category]) / 2))
    return best_category, round(confidence, 2), matches[best_category]


# ---------------------------------------------------------------------------
# Strategy 2: TF-IDF + classifier (optional, needs training + scikit-learn)
# ---------------------------------------------------------------------------

class DocumentTypeClassifier:
    """
    Thin wrapper around sklearn's TfidfVectorizer + LogisticRegression.
    Import of sklearn is deferred into __init__ / train() so this whole
    module still imports fine even if scikit-learn isn't installed and
    you only ever use the keyword-rule path.
    """

    def __init__(self):
        self.vectorizer = None
        self.model = None

    def train(self, texts: List[str], labels: List[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),   # unigrams + bigrams - "opening balance" as one feature, not two
            stop_words="english",
        )
        X = self.vectorizer.fit_transform(texts)
        self.model = LogisticRegression(max_iter=1000)
        self.model.fit(X, labels)
        return self

    def predict(self, text: str) -> Tuple[str, float]:
        if self.model is None:
            raise RuntimeError("Classifier not trained/loaded yet.")
        X = self.vectorizer.transform([text])
        pred = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]
        confidence = float(max(proba))
        return pred, round(confidence, 3)

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "model": self.model}, f)

    @classmethod
    def load(cls, path: str) -> "DocumentTypeClassifier":
        clf = cls()
        with open(path, "rb") as f:
            data = pickle.load(f)
        clf.vectorizer = data["vectorizer"]
        clf.model = data["model"]
        return clf


DEFAULT_MODEL_PATH = Path(__file__).parent / "classifier_model.pkl"

_cached_ml_classifier: Optional[DocumentTypeClassifier] = None
_ml_load_attempted = False


def _get_ml_classifier() -> Optional[DocumentTypeClassifier]:
    """Lazily loads the trained model file once, caches it. Returns None
    (silently) if no model file exists or scikit-learn isn't installed -
    callers fall back to keyword rules in that case."""
    global _cached_ml_classifier, _ml_load_attempted
    if _ml_load_attempted:
        return _cached_ml_classifier
    _ml_load_attempted = True
    if DEFAULT_MODEL_PATH.exists():
        try:
            _cached_ml_classifier = DocumentTypeClassifier.load(str(DEFAULT_MODEL_PATH))
        except Exception:
            _cached_ml_classifier = None
    return _cached_ml_classifier


# ---------------------------------------------------------------------------
# Public entry point: combines both strategies
# ---------------------------------------------------------------------------

def classify_document(text: str, keyword_confidence_floor: float = 0.3) -> Dict:
    """
    1. Try keyword rules first - if confident enough, trust it (fast,
       explainable, and correct on the exact phrasing it was written for).
    2. Otherwise, fall back to the trained TF-IDF model if one has been
       trained and saved (see train_classifier.py) - useful when the
       document uses wording the keyword list doesn't happen to cover.
    3. Otherwise, "unknown".

    Returns a dict rather than a bare string so the caller can see *why*
    a decision was made - important for a system where "silently guessed
    wrong" is worse than "flagged as unknown".
    """
    category, confidence, matched = classify_by_keywords(text)
    if category != "unknown" and confidence >= keyword_confidence_floor:
        return {"category": category, "method": "keyword_rules", "confidence": confidence, "matched_phrases": matched}

    ml = _get_ml_classifier()
    if ml is not None:
        try:
            ml_category, ml_confidence = ml.predict(text)
            return {"category": ml_category, "method": "tfidf_model", "confidence": ml_confidence, "matched_phrases": []}
        except Exception:
            pass

    # keyword rules found *something* but weren't confident, and no ML
    # model available/agreed - return the weak keyword guess rather than
    # nothing, but be honest that confidence is low.
    if category != "unknown":
        return {"category": category, "method": "keyword_rules_low_confidence", "confidence": confidence, "matched_phrases": matched}

    return {"category": "unknown", "method": "none", "confidence": 0.0, "matched_phrases": []}
