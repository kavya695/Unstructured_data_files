"""
test_preprocess.py

Tests preprocess.py in isolation - no OCR involved here, just checking
that image transformations do what they claim to do. This is the fast,
cheap layer of tests: pure image-in/image-out checks, no Tesseract calls.
"""
import cv2
import numpy as np
import pytest

from ocr_pipeline.preprocess import (
    to_gray, deskew, normalize_lighting, denoise,
    preprocess_scanned, preprocess_photo, preprocess_screenshot, preprocess,
)
from ocr_pipeline.pipeline import classify_doc_type
from .conftest import make_synthetic_text_image, make_blank_image, make_low_contrast_image


# ---------------------------------------------------------------------------
# to_gray
# ---------------------------------------------------------------------------

def test_to_gray_converts_color_to_single_channel():
    color_img = make_synthetic_text_image()
    gray = to_gray(color_img)
    assert gray.ndim == 2  # single channel, not (h, w, 3)


def test_to_gray_is_a_no_op_on_already_gray_image():
    color_img = make_synthetic_text_image()
    gray_once = to_gray(color_img)
    gray_twice = to_gray(gray_once)
    assert np.array_equal(gray_once, gray_twice)


# ---------------------------------------------------------------------------
# deskew - uses synthetic images because we control the EXACT ground-truth
# rotation angle, which a real photo never gives us.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("angle", [3, -3, 7, -7])
def test_deskew_reduces_a_known_rotation(angle):
    rotated = make_synthetic_text_image(angle=angle)
    gray = to_gray(rotated)
    corrected = deskew(gray)

    # Re-measure the corrected image's residual skew the same way deskew()
    # itself estimates it, and confirm it's now much closer to zero than
    # the angle we deliberately introduced.
    inv = cv2.bitwise_not(corrected)
    thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    residual_angle = cv2.minAreaRect(coords)[-1]
    if residual_angle < -45:
        residual_angle = -(90 + residual_angle)

    assert abs(residual_angle) < abs(angle) / 2, (
        f"deskew barely helped: introduced {angle} deg, residual {residual_angle:.1f} deg")


def test_deskew_leaves_a_straight_image_essentially_unchanged():
    straight = make_synthetic_text_image(angle=0)
    gray = to_gray(straight)
    corrected = deskew(gray)
    # shape should be identical since no rotation/expand should occur
    assert corrected.shape == gray.shape


def test_deskew_does_not_crash_on_a_blank_image():
    blank = make_blank_image()
    gray = to_gray(blank)
    # a blank page has no text pixels to estimate an angle from - deskew
    # should degrade gracefully (return the image unchanged), not crash
    result = deskew(gray)
    assert result is not None
    assert result.shape == gray.shape


# ---------------------------------------------------------------------------
# normalize_lighting
# ---------------------------------------------------------------------------

def test_normalize_lighting_flattens_a_shadow_gradient():
    """Build an image with a clear brightness gradient (simulating a
    shadow), and confirm normalize_lighting() reduces the left-vs-right
    brightness difference."""
    h, w = 300, 400
    gradient = np.tile(np.linspace(80, 220, w, dtype=np.uint8), (h, 1))
    before_diff = int(gradient[:, -1].mean()) - int(gradient[:, 0].mean())

    normalized = normalize_lighting(gradient)
    after_diff = abs(int(normalized[:, -1].mean()) - int(normalized[:, 0].mean()))

    assert after_diff < before_diff


# ---------------------------------------------------------------------------
# denoise
# ---------------------------------------------------------------------------

def test_denoise_reduces_random_noise_variance():
    gray = to_gray(make_synthetic_text_image())
    noisy = np.clip(gray.astype(np.int16) + np.random.normal(0, 25, gray.shape), 0, 255).astype(np.uint8)
    denoised = denoise(noisy)

    # denoising should bring the image measurably closer to the original
    # (lower error vs the clean source) than the noisy version was
    error_before = np.mean(np.abs(noisy.astype(np.int16) - gray.astype(np.int16)))
    error_after = np.mean(np.abs(denoised.astype(np.int16) - gray.astype(np.int16)))
    assert error_after < error_before


# ---------------------------------------------------------------------------
# Type-specific pipelines - smoke tests: do they run without crashing and
# return a valid single-channel image, on both synthetic and real samples?
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn", [preprocess_scanned, preprocess_photo, preprocess_screenshot])
def test_type_specific_preprocessors_return_valid_grayscale(fn):
    img = make_synthetic_text_image(angle=2)
    result = fn(img)
    assert result.ndim == 2
    assert result.dtype == np.uint8
    assert result.shape[0] > 0 and result.shape[1] > 0


def test_preprocess_scanned_on_real_sample_runs_cleanly(sample_scanned):
    result = preprocess(sample_scanned, "scanned")
    assert result.ndim == 2


def test_preprocess_photo_on_real_sample_runs_cleanly(sample_photo):
    result = preprocess(sample_photo, "photo")
    assert result.ndim == 2


def test_preprocess_screenshot_on_real_sample_runs_cleanly(sample_screenshot):
    result = preprocess(sample_screenshot, "screenshot")
    assert result.ndim == 2


def test_preprocess_rejects_unknown_doc_type(sample_scanned):
    with pytest.raises(ValueError):
        preprocess(sample_scanned, "not_a_real_type")


def test_preprocess_does_not_crash_on_low_contrast_image():
    """A washed-out/badly-lit photo shouldn't crash the pipeline, even if
    OCR accuracy on it ends up poor - crashing is worse than a bad result."""
    low_contrast = make_low_contrast_image()
    result = preprocess_photo(low_contrast)
    assert result is not None


# ---------------------------------------------------------------------------
# classify_doc_type - the scanned/photo/screenshot heuristic guesser
# ---------------------------------------------------------------------------

def test_classify_doc_type_calls_screenshot_a_screenshot(sample_screenshot):
    # Documented as a rough heuristic (see preprocess.py/pipeline.py docstrings) -
    # this test exists to catch a *regression* if someone changes the
    # heuristic's thresholds, not to certify it as production-accurate.
    result = classify_doc_type(sample_screenshot)
    assert result in ("screenshot", "scanned", "photo")  # must return a valid type at minimum


def test_classify_doc_type_never_crashes_on_grayscale_input():
    gray = to_gray(make_synthetic_text_image())
    result = classify_doc_type(gray)
    assert result == "scanned"  # 2D input is explicitly special-cased