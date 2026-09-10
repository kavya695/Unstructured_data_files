"""
preprocess.py

Input-type-specific image preprocessing.

Each function takes a raw image (numpy BGR array, as read by cv2.imread)
and returns a cleaned-up numpy array ready for OCR.

Three entry points, matching the three real-world source types:
    - preprocess_scanned(img)   : flatbed/ADF scans - mostly flat already
    - preprocess_photo(img)     : phone camera photos - needs deskew/crop/lighting fix
    - preprocess_screenshot(img): app/dashboard screenshots - minimal work needed
"""

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def to_gray(img):
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def deskew(gray):
    """Estimate and correct small rotation using the minAreaRect of text pixels."""
    inv = cv2.bitwise_not(gray)
    thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 20:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    # Ignore near-zero corrections and wild outliers (bad estimate)
    if abs(angle) < 0.1 or abs(angle) > 20:
        return gray
    (h, w) = gray.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                           borderMode=cv2.BORDER_REPLICATE)


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def find_document_contour(gray):
    """Try to find the 4-corner outline of a page within a photo."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    edged = cv2.dilate(edged, None, iterations=2)
    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        area = cv2.contourArea(approx)
        if len(approx) == 4 and area > 0.2 * gray.shape[0] * gray.shape[1]:
            return approx.reshape(4, 2)
    return None


def perspective_correct(img, gray):
    """If a page-like quadrilateral is found, warp it to a top-down rectangle.
    Falls back to the original image if no confident contour is found."""
    quad = find_document_contour(gray)
    if quad is None:
        return img

    rect = order_points(quad.astype("float32"))
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(max(widthA, widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(max(heightA, heightB))

    if maxWidth < 100 or maxHeight < 100:
        return img

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (maxWidth, maxHeight))


def normalize_lighting(gray):
    """Flatten uneven lighting/shadows using large-kernel background estimation."""
    bg = cv2.GaussianBlur(gray, (0, 0), sigmaX=25, sigmaY=25)
    diff = cv2.divide(gray, bg, scale=255)
    return diff


def denoise(gray):
    return cv2.fastNlMeansDenoising(gray, h=10)


def sharpen(gray):
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(gray, -1, kernel)


def binarize_adaptive(gray):
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def preprocess_scanned(img):
    """Scans are usually already flat/cropped. Fix: minor skew, light denoise,
    contrast normalization. Avoid aggressive binarization - it can wreck
    tesseract's built-in layout analysis for tables."""
    gray = to_gray(img)
    gray = deskew(gray)
    gray = normalize_lighting(gray)
    gray = denoise(gray)
    gray = cv2.convertScaleAbs(gray, alpha=1.15, beta=0)  # mild contrast boost
    return gray


def preprocess_photo(img):
    """Photos need the most work: crop out background, correct perspective,
    flatten shadows, denoise, sharpen."""
    gray = to_gray(img)
    warped_color = perspective_correct(img, gray)
    gray = to_gray(warped_color)
    gray = deskew(gray)
    gray = normalize_lighting(gray)
    gray = denoise(gray)
    gray = sharpen(gray)
    gray = cv2.convertScaleAbs(gray, alpha=1.2, beta=10)
    return gray


def preprocess_screenshot(img):
    """Screenshots are already crisp and correctly oriented. Just upscale
    slightly if small (helps OCR on small UI fonts) and ensure grayscale."""
    gray = to_gray(img)
    h, w = gray.shape
    if max(h, w) < 1400:
        scale = 1400 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return gray


PREPROCESSORS = {
    "scanned": preprocess_scanned,
    "photo": preprocess_photo,
    "screenshot": preprocess_screenshot,
}


def preprocess(img, doc_type):
    if doc_type not in PREPROCESSORS:
        raise ValueError(f"Unknown doc_type '{doc_type}', expected one of {list(PREPROCESSORS)}")
    return PREPROCESSORS[doc_type](img)
