"""
test_quality.py

Tests quality.py's blur/brightness/blank detection. Thresholds in
quality.py were calibrated against real measured Tesseract behavior (see
comments in that file) - these tests confirm the module correctly
classifies clearly-good and clearly-bad images relative to those
thresholds, and catches a regression if someone changes them carelessly.
"""
import cv2
import numpy as np
import pytest

from ocr_pipeline.preprocess import to_gray
from ocr_pipeline.quality import (
    compute_blur_score, compute_brightness, compute_contrast,
    is_blank_image, assess_image_quality,
    BLUR_SEVERE_THRESHOLD, BLUR_MODERATE_THRESHOLD,
)
from .conftest import make_synthetic_text_image, make_blank_image


# ---------------------------------------------------------------------------
# Real samples should all read as good quality - this is the most important
# sanity check: the feature must not falsely flag clean, real input.
# ---------------------------------------------------------------------------

def test_real_scanned_sample_is_not_flagged_as_low_quality(sample_scanned):
    gray = to_gray(sample_scanned)
    result = assess_image_quality(gray)
    assert result["recommend_reject"] is False
    assert result["is_blank"] is False
    assert result["quality_score"] > 80


def test_real_screenshot_sample_is_not_flagged_as_low_quality(sample_screenshot):
    gray = to_gray(sample_screenshot)
    result = assess_image_quality(gray)
    assert result["recommend_reject"] is False
    assert result["quality_score"] > 80


def test_real_photo_sample_is_not_rejected_despite_its_built_in_blur(sample_photo):
    """sample_2 has deliberate blur/shadow baked in during generation, and
    OCR still recovers it fine (~87% confidence in earlier pipeline tests) -
    it should read as imperfect, not as reject-worthy."""
    gray = to_gray(sample_photo)
    result = assess_image_quality(gray)
    assert result["recommend_reject"] is False


# ---------------------------------------------------------------------------
# Deliberately bad synthetic images should be caught
# ---------------------------------------------------------------------------

def test_heavily_blurred_image_is_flagged_severe(sample_scanned):
    gray = to_gray(sample_scanned)
    heavily_blurred = cv2.GaussianBlur(gray, (25, 25), 0)
    result = assess_image_quality(heavily_blurred)
    assert "severely_blurred" in result["issues"]
    assert result["recommend_reject"] is True


def test_blank_white_image_is_flagged_blank():
    blank = to_gray(make_blank_image(color=255))
    result = assess_image_quality(blank)
    assert result["is_blank"] is True
    assert result["recommend_reject"] is True
    assert result["quality_score"] == 0.0


def test_blank_black_image_is_flagged_blank():
    blank = to_gray(make_blank_image(color=0))
    result = assess_image_quality(blank)
    assert result["is_blank"] is True


def test_extremely_dark_image_is_flagged_too_dark(sample_scanned):
    gray = to_gray(sample_scanned)
    # Multiply toward black rather than subtract a fixed delta - subtracting
    # a constant clips at 0 and, on a bright-background source image, can
    # land above the threshold without actually producing a dark image.
    # Multiplying guarantees a genuinely low mean regardless of the source.
    very_dark = (gray.astype(np.float32) * 0.05).astype(np.uint8)
    result = assess_image_quality(very_dark)
    assert "too_dark" in result["issues"]


def test_extremely_bright_image_is_flagged(sample_scanned):
    gray = to_gray(sample_scanned)
    very_bright = np.clip(gray.astype(np.int16) + 200, 0, 255).astype(np.uint8)
    result = assess_image_quality(very_bright)
    assert "too_bright_or_blown_out" in result["issues"]


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------

def test_blur_score_is_higher_for_sharper_image():
    gray = to_gray(make_synthetic_text_image())
    sharp_score = compute_blur_score(gray)
    blurred = cv2.GaussianBlur(gray, (15, 15), 0)
    blurred_score = compute_blur_score(blurred)
    assert sharp_score > blurred_score


def test_is_blank_image_true_for_uniform_image():
    blank = to_gray(make_blank_image())
    assert is_blank_image(blank) is True


def test_is_blank_image_false_for_real_text_image():
    gray = to_gray(make_synthetic_text_image())
    assert is_blank_image(gray) is False


def test_quality_score_ranges_between_0_and_100(sample_scanned, sample_photo):
    for gray in [to_gray(sample_scanned), to_gray(sample_photo)]:
        result = assess_image_quality(gray)
        assert 0.0 <= result["quality_score"] <= 100.0


def test_thresholds_are_ordered_sensibly():
    """A basic sanity guard on the constants themselves - if someone edits
    quality.py and accidentally sets severe above moderate, every
    downstream classification would become nonsensical."""
    assert BLUR_SEVERE_THRESHOLD < BLUR_MODERATE_THRESHOLD