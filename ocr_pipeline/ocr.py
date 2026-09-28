"""
ocr.py

Runs Tesseract over a preprocessed image and returns word-level results
with bounding boxes, then groups words back into lines - this is the
"Text + coordinates" stage of the pipeline.
"""

from dataclasses import dataclass, field
from typing import List
import pytesseract
from pytesseract import Output


@dataclass
class Word:
    text: str
    conf: float
    x: int
    y: int
    w: int
    h: int
    line_id: int  # (block, par, line) grouping key, unique per page


@dataclass
class Line:
    text: str
    words: List[Word] = field(default_factory=list)
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0


def run_ocr(gray_img, lang="eng", psm=6):
    """
    psm 6 = 'Assume a single uniform block of text' - good default for
    documents/statements. Use psm=4 for multi-column layouts, psm=11 for
    sparse text (e.g. scattered labels in a dashboard screenshot).
    """
    config = f"--oem 3 --psm {psm}"
    data = pytesseract.image_to_data(gray_img, lang=lang, config=config, output_type=Output.DICT)

    words: List[Word] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        line_id = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        words.append(Word(
            text=text,
            conf=conf,
            x=data["left"][i],
            y=data["top"][i],
            w=data["width"][i],
            h=data["height"][i],
            line_id=hash(line_id),
        ))
    return words


def group_into_lines(words: List[Word]) -> List[Line]:
    lines_map = {}
    for w in words:
        lines_map.setdefault(w.line_id, []).append(w)

    lines = []
    for line_id, ws in lines_map.items():
        ws = sorted(ws, key=lambda w: w.x)
        text = " ".join(w.text for w in ws)
        x0 = min(w.x for w in ws)
        y0 = min(w.y for w in ws)
        x1 = max(w.x + w.w for w in ws)
        y1 = max(w.y + w.h for w in ws)
        lines.append(Line(text=text, words=ws, x=x0, y=y0, w=x1 - x0, h=y1 - y0))

    lines.sort(key=lambda l: (l.y, l.x))
    return lines


def ocr_to_lines(gray_img, lang="eng", psm=6) -> List[Line]:
    words = run_ocr(gray_img, lang=lang, psm=psm)
    return group_into_lines(words)


def average_confidence(words: List[Word]) -> float:
    if not words:
        return 0.0
    return sum(w.conf for w in words) / len(words)
