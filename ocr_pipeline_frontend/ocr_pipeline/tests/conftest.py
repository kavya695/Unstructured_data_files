"""
conftest.py

Shared pytest fixtures for the image/OCR side of the pipeline
(preprocess.py + ocr.py). Anything text/extraction-related
(classify.py, extract.py, normalize.py) is deliberately out of scope here -
that's a separate team's responsibility per the current project split.

pytest auto-discovers this file - no imports needed elsewhere.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

# Make the ocr_pipeline package importable regardless of where pytest is
# run from (project root or inside tests/).
PACKAGE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PACKAGE_DIR.parent))

SAMPLES_DIR = PACKAGE_DIR


@pytest.fixture
def sample_scanned():
    """A clean scanned-style credit report - should be the easiest case:
    high OCR confidence, minimal preprocessing needed."""
    path = SAMPLES_DIR / "sample_1_scanned_credit_report.png"
    return cv2.imread(str(path))


@pytest.fixture
def sample_photo():
    """A phone-photo-style document with perspective warp, shadow, and
    blur baked in - the hardest of the three input types."""
    path = SAMPLES_DIR / "sample_2_document_photo.png"
    return cv2.imread(str(path))


@pytest.fixture
def sample_screenshot():
    """A crisp, undistorted dashboard screenshot - should need almost no
    preprocessing at all."""
    path = SAMPLES_DIR / "sample_3_financial_report_screenshot.png"
    return cv2.imread(str(path))


def make_synthetic_text_image(angle: float = 0.0, size=(600, 400)) -> np.ndarray:
    """
    Builds a plain white image with a few lines of black text, optionally
    rotated by `angle` degrees - used for deskew tests where we need to
    know the EXACT ground-truth rotation we introduced, rather than relying
    on a real photo where we don't actually know the true angle.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    for i, line in enumerate(["Account Number: 12345678", "Balance: Rs. 50,000", "Status: Active"]):
        d.text((40, 60 + i * 50), line, font=font, fill="black")

    if angle != 0.0:
        img = img.rotate(angle, expand=True, fillcolor="white")

    rgb = np.array(img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def make_blank_image(size=(400, 300), color=255) -> np.ndarray:
    """A blank/near-blank image - simulates a failed capture, a mostly-white
    page with no content, or a lens-cap-on photo."""
    return np.full((size[1], size[0], 3), color, dtype=np.uint8)


def make_low_contrast_image(size=(400, 300)) -> np.ndarray:
    """Text with very little contrast against its background - simulates
    a badly lit or washed-out photo."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, (200, 200, 200))
    d = ImageDraw.Draw(img)
    d.text((40, 130), "Balance: Rs. 10,000", fill=(180, 180, 180))
    rgb = np.array(img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)