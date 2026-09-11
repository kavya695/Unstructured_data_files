"""PDF -> list[str] (one string per page), OCR fallback for scanned pages."""
import io
import fitz  # PyMuPDF
import pytesseract
from PIL import Image


def _page_has_text(page) -> bool:
    return len(page.get_text().strip()) > 20


def extract_pdf(path: str, ocr_dpi: int = 300) -> list[str]:
    doc = fitz.open(path)
    page_texts = []
    for page in doc:
        if _page_has_text(page):
            page_texts.append(page.get_text())
        else:
            zoom = ocr_dpi / 72
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            page_texts.append(pytesseract.image_to_string(img))
    doc.close()
    return page_texts
