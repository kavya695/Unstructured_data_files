"""
generate_extra_samples.py

Generates 2 more synthetic (fake-data) sample documents so the document-type
classifier has more than one category to actually distinguish:

    sample_4_invoice.png
    sample_5_bank_statement.png

Run: python3 generate_extra_samples.py
"""
import random
from PIL import Image, ImageDraw, ImageFont

random.seed(7)
W, H = 1240, 1600


def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


FONT_TITLE = load_font(34, bold=True)
FONT_HEAD = load_font(24, bold=True)
FONT_BODY = load_font(20)
FONT_SMALL = load_font(16)


def make_invoice(path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 110], fill=(40, 40, 40))
    d.text((60, 30), "Acme Supplies Pvt. Ltd.", font=FONT_TITLE, fill="white")
    d.text((60, 75), "TAX INVOICE", font=FONT_SMALL, fill=(220, 220, 220))

    y = 150
    fields = [
        ("Invoice Number", "INV-2026-00871"),
        ("Invoice Date", "20/08/2026"),
        ("Due Date", "04/09/2026"),
        ("Bill To", "Ramesh Traders, Bengaluru"),
    ]
    for label, value in fields:
        d.text((60, y), f"{label}:", font=FONT_BODY, fill=(60, 60, 60))
        d.text((420, y), value, font=FONT_BODY, fill=(0, 0, 0))
        y += 40

    y += 20
    d.line([60, y, W - 60, y], fill=(180, 180, 180), width=1)
    y += 30
    d.text((60, y), "Item", font=FONT_HEAD, fill=(40, 40, 40))
    d.text((760, y), "Qty", font=FONT_HEAD, fill=(40, 40, 40))
    d.text((900, y), "Unit Price", font=FONT_HEAD, fill=(40, 40, 40))
    d.text((1080, y), "Amount", font=FONT_HEAD, fill=(40, 40, 40))
    y += 40
    d.line([60, y, W - 60, y], fill=(120, 120, 120), width=1)
    y += 20

    items = [
        ("Steel Bolts (Box of 100)", 4, 850),
        ("Hex Nuts (Box of 100)", 4, 620),
        ("Packing & Handling", 1, 300),
    ]
    for name, qty, price in items:
        d.text((60, y), name, font=FONT_BODY, fill=(0, 0, 0))
        d.text((760, y), str(qty), font=FONT_BODY, fill=(0, 0, 0))
        d.text((900, y), f"Rs. {price}", font=FONT_BODY, fill=(0, 0, 0))
        d.text((1080, y), f"Rs. {qty * price}", font=FONT_BODY, fill=(0, 0, 0))
        y += 38

    subtotal = sum(q * p for _, q, p in items)
    tax = round(subtotal * 0.18)
    total = subtotal + tax

    y += 20
    d.line([700, y, W - 60, y], fill=(120, 120, 120), width=1)
    y += 20
    d.text((900, y), "Subtotal:", font=FONT_BODY, fill=(0, 0, 0))
    d.text((1080, y), f"Rs. {subtotal}", font=FONT_BODY, fill=(0, 0, 0))
    y += 36
    d.text((900, y), "Tax (18% GST):", font=FONT_BODY, fill=(0, 0, 0))
    d.text((1080, y), f"Rs. {tax}", font=FONT_BODY, fill=(0, 0, 0))
    y += 36
    d.text((900, y), "Total:", font=FONT_HEAD, fill=(0, 0, 0))
    d.text((1080, y), f"Rs. {total}", font=FONT_HEAD, fill=(0, 0, 0))

    d.text((60, H - 60), "Thank you for your business. Payment due within 15 days.",
           font=FONT_SMALL, fill=(120, 120, 120))
    d.text((60, H - 35), "This is a synthetically generated sample document for software testing only.",
           font=FONT_SMALL, fill=(180, 60, 60))
    img.save(path, "PNG")


def make_bank_statement(path):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 110], fill=(15, 60, 40))
    d.text((60, 30), "Horizon Finance Bank", font=FONT_TITLE, fill="white")
    d.text((60, 75), "Account Statement (Sample)", font=FONT_SMALL, fill=(220, 235, 225))

    y = 150
    fields = [
        ("Account Holder", "Priya Sharma"),
        ("Account Number", "XXXXXXXX7734"),
        ("Statement Period", "01/08/2026 to 31/08/2026"),
        ("Opening Balance", "Rs. 1,84,320.50"),
        ("Closing Balance", "Rs. 1,64,940.75"),
    ]
    for label, value in fields:
        d.text((60, y), f"{label}:", font=FONT_BODY, fill=(40, 40, 40))
        d.text((420, y), value, font=FONT_BODY, fill=(0, 0, 0))
        y += 40

    y += 20
    d.line([60, y, W - 60, y], fill=(180, 180, 180), width=1)
    y += 30
    d.text((60, y), "Transaction History", font=FONT_HEAD, fill=(15, 60, 40))
    y += 45

    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    col_x = [60, 260, 700, 850, 1000]
    for h, x in zip(headers, col_x):
        d.text((x, y), h, font=FONT_HEAD, fill=(40, 40, 40))
    y += 35
    d.line([60, y, W - 60, y], fill=(120, 120, 120), width=1)
    y += 15

    rows = [
        ("01/08/2026", "Salary Credit - Acme Corp", "-", "75,000.00", "1,84,320.50"),
        ("03/08/2026", "EMI - Personal Loan", "12,450.00", "-", "1,71,870.50"),
        ("05/08/2026", "UPI - Grocery Mart", "2,340.00", "-", "1,69,530.50"),
        ("08/08/2026", "Interest Credit", "-", "410.25", "1,69,940.75"),
        ("12/08/2026", "ATM Withdrawal", "5,000.00", "-", "1,64,940.75"),
    ]
    for row in rows:
        for val, x in zip(row, col_x):
            d.text((x, y), val, font=FONT_BODY, fill=(0, 0, 0))
        y += 36

    d.text((60, H - 60), "IFSC: HORF0001234  |  Branch: MG Road, Bengaluru",
           font=FONT_SMALL, fill=(120, 120, 120))
    d.text((60, H - 35), "This is a synthetically generated sample document for software testing only.",
           font=FONT_SMALL, fill=(180, 60, 60))
    img.save(path, "PNG")


if __name__ == "__main__":
    make_invoice("sample_4_invoice.png")
    make_bank_statement("sample_5_bank_statement.png")
    print("Done: 2 additional sample images generated.")
