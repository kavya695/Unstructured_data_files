"""
train_classifier.py

Trains the TF-IDF + Logistic Regression document-type classifier
(see classify.py) and saves it to classifier_model.pkl.

You have two ways to get training data:

    1. REAL documents (recommended once you have them): put your OCR'd
       text + labels into a CSV with columns "text,label" and call
       train_from_csv() below.

    2. SYNTHETIC documents (what this script does by default): generates
       varied fake invoice / bank statement / credit report text using
       templates + randomized values, so you have *something* to train
       and test the pipeline with before real labeled data exists.
       Replace this with real data as soon as you can - synthetic text
       only teaches the model the vocabulary I thought to use.

Run:
    python3 train_classifier.py
"""
import random
from pathlib import Path
from classify import DocumentTypeClassifier

random.seed(0)

MODEL_PATH = Path(__file__).parent / "classifier_model.pkl"


# ---------------------------------------------------------------------------
# Synthetic corpus generation
# ---------------------------------------------------------------------------

VENDORS = ["Acme Supplies", "Ramesh Traders", "Global Hardware Co", "Sunrise Electronics", "Metro Stationers"]
BANKS = ["Horizon Finance Bank", "National Trust Bank", "Coastal Union Bank", "Meridian Bank"]
NAMES = ["Priya Sharma", "Rahul Verma", "Ananya Iyer", "Vikram Singh", "Neha Gupta"]


def rand_amount():
    return f"Rs. {random.randint(500, 500000):,}"


def rand_date():
    return f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/2026"


def rand_id(prefix):
    return f"{prefix}-{random.randint(1000,99999)}"


def gen_invoice_text():
    lines = [
        f"{random.choice(VENDORS)} Pvt. Ltd.",
        "TAX INVOICE",
        f"Invoice Number: {rand_id('INV')}",
        f"Invoice Date: {rand_date()}",
        f"Due Date: {rand_date()}",
        f"Bill To: {random.choice(NAMES)}",
        "Item Qty Unit Price Amount",
        f"Subtotal: {rand_amount()}",
        f"Tax (18% GST): {rand_amount()}",
        f"Total: {rand_amount()}",
        "Thank you for your business. Payment due within 15 days.",
    ]
    return "\n".join(lines)


def gen_bank_statement_text():
    lines = [
        random.choice(BANKS),
        "Account Statement",
        f"Account Holder: {random.choice(NAMES)}",
        f"Account Number: XXXXXXXX{random.randint(1000,9999)}",
        f"Statement Period: {rand_date()} to {rand_date()}",
        f"Opening Balance: {rand_amount()}",
        f"Closing Balance: {rand_amount()}",
        "Transaction History",
        "Date Description Debit Credit Balance",
        f"IFSC: {random.choice(['HORF','NTBK','CUBK','MRDN'])}000{random.randint(100,999)}",
    ]
    return "\n".join(lines)


def gen_credit_report_text():
    lines = [
        "CreditScore Bureau",
        "Consumer Credit Information Report",
        "Credit Account Details",
        f"Account Number: XXXXXXXX{random.randint(1000,9999)}",
        "Account Type: Personal Loan",
        f"Lender: {random.choice(BANKS)}",
        f"Date Opened: {rand_date()}",
        f"Sanctioned Amount: {rand_amount()}",
        f"Current Balance: {rand_amount()}",
        "Payment Status: Active - Current",
        f"Days Past Due: {random.choice([0,0,0,5,15])}",
        f"Credit Score: {random.randint(600,850)}",
    ]
    return "\n".join(lines)


GENERATORS = {
    "invoice": gen_invoice_text,
    "bank_statement": gen_bank_statement_text,
    "credit_report": gen_credit_report_text,
}


def build_synthetic_corpus(n_per_category: int = 60):
    texts, labels = [], []
    for category, gen_fn in GENERATORS.items():
        for _ in range(n_per_category):
            texts.append(gen_fn())
            labels.append(category)
    return texts, labels


# ---------------------------------------------------------------------------
# Training entry points
# ---------------------------------------------------------------------------

def train_from_synthetic(n_per_category: int = 60, test_fraction: float = 0.2):
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    texts, labels = build_synthetic_corpus(n_per_category)
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_fraction, random_state=0, stratify=labels)

    clf = DocumentTypeClassifier()
    clf.train(X_train, y_train)

    preds = [clf.predict(t)[0] for t in X_test]
    print("Holdout accuracy report:")
    print(classification_report(y_test, preds))

    clf.save(str(MODEL_PATH))
    print(f"Saved trained model to {MODEL_PATH}")
    return clf


def train_from_csv(csv_path: str, text_col: str = "text", label_col: str = "label"):
    """Use this once you have real labeled documents. CSV needs at least
    the two columns named above (header row required)."""
    import csv as csv_module

    texts, labels = [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            texts.append(row[text_col])
            labels.append(row[label_col])

    clf = DocumentTypeClassifier()
    clf.train(texts, labels)
    clf.save(str(MODEL_PATH))
    print(f"Trained on {len(texts)} real examples. Saved to {MODEL_PATH}")
    return clf


if __name__ == "__main__":
    train_from_synthetic()
