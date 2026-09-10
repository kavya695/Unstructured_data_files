"""
quality.py

Answers a question preprocess.py and ocr.py don't: "is this image even
worth processing, and how much should the result be trusted?"

Thresholds below were NOT guessed - they came from directly measuring how
real Tesseract OCR confidence and word-recovery degrade as blur/brightness
are pushed to extremes on a real sample document. See the comments next to
each threshold for the actual numbers observed. If you recalibrate these
against your own real documents later, this is the file to change.

Key finding from that calibration: blur is the dominant real quality
signal. Tesseract does its own internal thresholding, so it tolerates a
surprisingly wide brightness/contrast range - a document doesn't become
unreadable until brightness is near-blown-out or near-blank. Blur, on the
other hand, silently destroys word recovery well before OCR confidence
itself visibly drops (94 words found -> 12 words found, while confidence
still read a false-reassuring 95%) - which is why this module leans on
blur as the primary "reject or flag" signal, not confidence alone.
"""

import cv2
import numpy as np
from typing import Dict


# Calibration reference (Laplacian variance -> real outcome, measured on a
# clean 1240x1600 scanned document):
#   score ~1160 (native, sharp)        -> 93% confidence, 94/94 words found
#   score ~78   (light blur)           -> 93% confidence, 52/94 words found
#   score ~8.5  (moderate blur)        -> 95% confidence, only 12/94 words found (!)
#   score ~2.3  (heavy blur)           -> 77% confidence, 12/94 words found
#   score ~0.9  (severe blur)          -> 48% confidence, 15/94 words found
#   score ~0.5  (extreme blur)         -> 25% confidence, 4/94 words found
# The 12-word cliff between "78" and "8.5" is why MODERATE sits well above
# where confidence itself starts falling - confidence alone would miss it.
BLUR_SEVERE_THRESHOLD = 10.0    # below this: expect major content loss, likely unusable
BLUR_MODERATE_THRESHOLD = 60.0  # below this: some content loss risk, flag for review

# Brightness (0-255 mean). Real measurement: OCR stayed >70% confident down
# to mean=37 (quite dark) and up to mean=252 (quite bright) - only truly
# extreme values matter here.
BRIGHTNESS_TOO_DARK = 25.0
BRIGHTNESS_TOO_BRIGHT = 250.0

# A uniform/blank image (blank page, lens cap, failed capture) has almost
# zero pixel variation - real text-bearing images measured std >= ~50.
BLANK_STD_THRESHOLD = 3.0


def compute_blur_score(gray: np.ndarray) -> float:
    """Laplacian variance: how much high-frequency detail (sharp edges) an
    image has. Sharp text has lots of edges -> high variance. Blur smooths
    edges away -> low variance. This is the standard, cheap way to measure
    blur without needing a reference 'sharp' version to compare against."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_brightness(gray: np.ndarray) -> float:
    return float(gray.mean())


def compute_contrast(gray: np.ndarray) -> float:
    return float(gray.std())


def is_blank_image(gray: np.ndarray) -> bool:
    """A near-uniform image (all one color/shade) has essentially no
    content - this catches lens-cap photos, failed scans, and blank pages
    before wasting time running OCR on them at all."""
    return compute_contrast(gray) < BLANK_STD_THRESHOLD


def assess_image_quality(gray: np.ndarray) -> Dict:
    """
    Runs cheap pixel-level checks BEFORE OCR - use this to decide whether
    it's even worth running the (much more expensive) OCR step, and to
    explain *why* a result should or shouldn't be trusted.

    Returns a dict with individual metrics, a list of specific issues
    found (empty list = no concerns), a single 0-100 quality_score for
    easy sorting/thresholding, and recommend_reject as a blunt yes/no.
    """
    blank = is_blank_image(gray)
    blur = compute_blur_score(gray)
    brightness = compute_brightness(gray)
    contrast = compute_contrast(gray)

    issues = []
    if blank:
        issues.append("blank_or_uniform_image")
    elif blur < BLUR_SEVERE_THRESHOLD:
        issues.append("severely_blurred")
    elif blur < BLUR_MODERATE_THRESHOLD:
        issues.append("mildly_blurred")

    if brightness < BRIGHTNESS_TOO_DARK:
        issues.append("too_dark")
    elif brightness > BRIGHTNESS_TOO_BRIGHT:
        issues.append("too_bright_or_blown_out")

    if blank:
        quality_score = 0.0
    else:
        # blur contributes most of the score (it's the strongest real
        # signal per the calibration above); brightness only penalizes
        # at the extremes, matching how little it actually hurt OCR.
        blur_component = min(100.0, (blur / BLUR_MODERATE_THRESHOLD) * 100.0)
        brightness_component = 100.0 if BRIGHTNESS_TOO_DARK <= brightness <= BRIGHTNESS_TOO_BRIGHT else 40.0
        quality_score = round(min(100.0, 0.75 * blur_component + 0.25 * brightness_component), 1)

    return {
        "blur_score": round(blur, 1),
        "brightness": round(brightness, 1),
        "contrast": round(contrast, 1),
        "is_blank": blank,
        "issues": issues,
        "quality_score": quality_score,
        # a hard "don't bother OCR-ing this" signal for blank/severely blurred input,
        # separate from quality_score since a caller might want the number
        # even when also rejecting outright.
        "recommend_reject": blank or blur < BLUR_SEVERE_THRESHOLD,
    }