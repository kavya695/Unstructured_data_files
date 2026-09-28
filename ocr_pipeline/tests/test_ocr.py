"""
test_ocr.py

Tests ocr.py against real sample images. These are slower than
test_preprocess.py (they actually invoke Tesseract), so keep this file
focused on the OCR layer's own behavior - not field extraction, which is
out of scope for the image/OCR side of this project.
"""
import pytest

from ocr_pipeline.preprocess import preprocess
from ocr_pipeline.ocr import run_ocr, group_into_lines, ocr_to_lines, average_confidence


# ---------------------------------------------------------------------------
# Confidence thresholds below are deliberately loose - real OCR confidence
# varies run to run and with tesseract version. These catch a REGRESSION
# (e.g. someone breaks preprocessing and confidence craters to 20%), not
# small day-to-day fluctuation.
# ---------------------------------------------------------------------------

def test_ocr_produces_words_on_clean_scanned_sample(sample_scanned):
    processed = preprocess(sample_scanned, "scanned")
    words = run_ocr(processed)
    assert len(words) > 10  # a full-page document should yield many words


def test_ocr_confidence_is_high_on_clean_scanned_sample(sample_scanned):
    processed = preprocess(sample_scanned, "scanned")
    words = run_ocr(processed)
    conf = average_confidence(words)
    assert conf > 70, f"expected high confidence on a clean scan, got {conf}"


def test_ocr_still_produces_words_on_harder_photo_sample(sample_photo):
    """The photo sample has perspective warp, shadow, and blur baked in -
    confidence should be lower than the scanned sample, but OCR shouldn't
    fail outright."""
    processed = preprocess(sample_photo, "photo")
    words = run_ocr(processed)
    conf = average_confidence(words)
    assert len(words) > 5
    assert conf > 40, f"OCR confidence too low even for the harder photo case: {conf}"


def test_ocr_finds_known_text_on_scanned_sample(sample_scanned):
    """Spot-check that a specific, known phrase from the sample actually
    comes through OCR - catches a broken preprocessing step that produces
    garbage even if confidence scores look superficially fine."""
    processed = preprocess(sample_scanned, "scanned")
    lines = ocr_to_lines(processed)
    full_text = " ".join(l.text for l in lines).lower()
    assert "account" in full_text
    assert "credit" in full_text


# ---------------------------------------------------------------------------
# group_into_lines
# ---------------------------------------------------------------------------

def test_group_into_lines_returns_lines_sorted_top_to_bottom(sample_scanned):
    processed = preprocess(sample_scanned, "scanned")
    lines = ocr_to_lines(processed)
    y_positions = [l.y for l in lines]
    assert y_positions == sorted(y_positions), "lines should be ordered top-to-bottom"


def test_group_into_lines_handles_empty_word_list():
    result = group_into_lines([])
    assert result == []


def test_each_line_has_matching_word_list_and_text(sample_scanned):
    processed = preprocess(sample_scanned, "scanned")
    lines = ocr_to_lines(processed)
    for line in lines:
        assert len(line.words) > 0
        # the line's text should be the words joined with spaces, in order
        assert line.text == " ".join(w.text for w in line.words)


# ---------------------------------------------------------------------------
# average_confidence
# ---------------------------------------------------------------------------

def test_average_confidence_of_empty_list_is_zero():
    assert average_confidence([]) == 0.0


def test_psm_parameter_is_respected_without_crashing(sample_scanned):
    """Different documents need different Tesseract page-segmentation
    modes (see ocr.py docstring) - confirm switching psm doesn't break
    anything, even if we're not asserting which mode is 'best' here."""
    processed = preprocess(sample_scanned, "scanned")
    for psm in (4, 6, 11):
        words = run_ocr(processed, psm=psm)
        assert isinstance(words, list)  # should always return a list, never crash