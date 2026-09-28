"""PDF -> list[str] (one string per page), OCR fallback for scanned pages."""
import io
import os
import shutil
import fitz  # PyMuPDF
import pytesseract
from PIL import Image


def _autoconfigure_tesseract():
    """If tesseract isn't already on PATH, try the default Windows install
    location so users don't have to edit their system PATH manually."""
    if shutil.which("tesseract"):
        return  # already on PATH, nothing to do
    windows_defaults = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in windows_defaults:
        if os.path.isfile(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


_autoconfigure_tesseract()


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
            try:
                page_texts.append(pytesseract.image_to_string(img))
            except pytesseract.TesseractNotFoundError:
                raise RuntimeError(
                    "Tesseract OCR isn't installed or isn't on your PATH. "
                    "This PDF has scanned/image pages that need OCR to read. "
                    "Install it from https://github.com/UB-Mannheim/tesseract/wiki "
                    "(Windows) and either add it to PATH or install to the default "
                    "location (C:\\Program Files\\Tesseract-OCR) so this script can "
                    "find it automatically. See README.md for full instructions."
                ) from None
    doc.close()
    return page_texts
