"""
Font size compliance checking — reference-card calibration method.

This is deliberately a SEPARATE feature from the OCR/declaration-extraction
pipeline (cv_service.py / ocr_service.py / declaration_service.py). The
brief asks for font size checking to live behind its own button, because it
solves a different problem: turning an OCR bounding-box height in *pixels*
(which depends entirely on how close/zoomed-in the photo was) into a real
physical height in *millimetres*, which is what Rule 8 of the Legal
Metrology (Packaged Commodities) Rules, 2011 actually regulates.

Method: the inspector places a standard reference card (by default an
ISO/IEC 7810 ID-1 card — a debit/credit/Aadhaar-style card, 85.60mm x
53.98mm) flat against the package, next to the declaration being checked,
and captures ONE photo containing both. This module:

  1. Finds the card in the image via contour detection (`detect_reference_card`)
     — it looks for a well-formed quadrilateral whose *aspect ratio* matches
     a real ID-1 card, not just "the biggest rectangle", so it doesn't
     confuse the card with the package outline.
  2. Derives a millimetres-per-pixel scale from the card's measured pixel
     dimensions and its known real-world size.
  3. Runs OCR (see ocr_service.py — English + Hindi) on the same image and
     converts every detected text line's pixel bounding-box height into a
     physical height in millimetres using that scale.
  4. Compares each measured height against the configurable minimum height
     standards in `FontSizeStandardORM` (seeded from
     app/rules/font_size_standards.yaml, editable by an Administrator — the
     same dynamic-rule pattern as rule_engine.py) and reports PASS/FAIL.

If no card is confidently detected, this returns a NEEDS_CARD result rather
than fabricating a scale — a wrong calibration is worse than no calibration.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import get_settings
from app.services import ocr_service
from app.services.ocr_service import OcrWord

settings = get_settings()

# A real ID-1 card's long/short side ratio (85.60 / 53.98 ≈ 1.586). Any
# detected quadrilateral within this tolerance of the ratio (in either
# orientation) is treated as a candidate card.
_ID1_ASPECT_RATIO = settings.reference_card_width_mm / settings.reference_card_height_mm
_ASPECT_TOLERANCE = 0.18


@dataclass
class CardDetection:
    found: bool
    px_per_mm: float | None
    corners: list[list[float]] | None
    confidence: float
    message: str


@dataclass
class FontMeasurement:
    text: str
    confidence: float
    box: dict
    height_px: float
    height_mm: float


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def detect_reference_card(
    image: np.ndarray,
    card_width_mm: float | None = None,
    card_height_mm: float | None = None,
) -> CardDetection:
    """
    Locates a rectangular reference card by aspect ratio (not just size), so
    it isn't fooled by the (usually larger, non-card-shaped) package outline.
    Tries every reasonably large quadrilateral contour and keeps the one
    whose measured side ratio is closest to a real card's ratio.
    """
    card_width_mm = card_width_mm or settings.reference_card_width_mm
    card_height_mm = card_height_mm or settings.reference_card_height_mm
    target_ratio = card_width_mm / card_height_mm

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]

    best: tuple[float, np.ndarray, float, float] | None = None  # (score, rect, w_px, h_px)

    for contour in contours:
        area = cv2.contourArea(contour)
        # A usable reference card should be legible in-frame but is not the
        # whole package — reject specks and near-full-frame contours alike.
        if area < 0.01 * image_area or area > 0.6 * image_area:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue

        pts = approx.reshape(4, 2).astype("float32")
        rect = _order_points(pts)
        (tl, tr, br, bl) = rect
        width_px = (np.linalg.norm(br - bl) + np.linalg.norm(tr - tl)) / 2
        height_px = (np.linalg.norm(tr - br) + np.linalg.norm(tl - bl)) / 2
        if width_px < 30 or height_px < 30:
            continue

        ratio = max(width_px, height_px) / min(width_px, height_px)
        ratio_error = abs(ratio - target_ratio) / target_ratio
        if ratio_error > _ASPECT_TOLERANCE:
            continue

        # Prefer the candidate whose ratio is the closest match; among close
        # matches, prefer the larger one (more pixels -> a more precise scale).
        score = (1 - ratio_error) * area
        if best is None or score > best[0]:
            best = (score, rect, width_px, height_px)

    if best is None:
        return CardDetection(
            found=False,
            px_per_mm=None,
            corners=None,
            confidence=0.0,
            message=(
                "No reference card was confidently detected. Make sure the card lies flat, fully "
                "visible, well-lit, and next to the text being measured, then retake the photo."
            ),
        )

    _, rect, width_px, height_px = best
    # Match the longer detected side to the card's longer physical side,
    # regardless of whether the card was photographed in portrait or
    # landscape orientation.
    long_px, short_px = max(width_px, height_px), min(width_px, height_px)
    long_mm, short_mm = max(card_width_mm, card_height_mm), min(card_width_mm, card_height_mm)
    px_per_mm = ((long_px / long_mm) + (short_px / short_mm)) / 2

    ratio = long_px / short_px
    ratio_error = abs(ratio - target_ratio) / target_ratio
    confidence = max(0.0, 1 - (ratio_error / _ASPECT_TOLERANCE)) * 0.9 + 0.1

    return CardDetection(
        found=True,
        px_per_mm=float(px_per_mm),
        corners=rect.tolist(),
        confidence=round(float(confidence), 2),
        message="Reference card detected — calibration derived from its known physical size.",
    )


def measure_text_heights(words: list[OcrWord], px_per_mm: float) -> list[FontMeasurement]:
    """Converts every OCR word's pixel bounding-box height into millimetres."""
    measurements: list[FontMeasurement] = []
    for word in words:
        height_px = ocr_service.estimate_text_height_px(word)
        if height_px <= 0:
            continue
        xs = [p[0] for p in word.box]
        ys = [p[1] for p in word.box]
        measurements.append(
            FontMeasurement(
                text=word.text,
                confidence=word.confidence,
                box={"x": min(xs), "y": min(ys), "width": max(xs) - min(xs), "height": max(ys) - min(ys)},
                height_px=round(height_px, 2),
                height_mm=round(height_px / px_per_mm, 3),
            )
        )
    return measurements


def evaluate_against_standards(
    measurements: list[FontMeasurement], standards: list[dict]
) -> list[dict]:
    """
    Compares each measured text line's height against every enabled minimum-
    height standard whose declaration type keyword appears in the line's own
    text (so "MRP Rs. 199" is checked against the MRP standard, a plain
    ingredient list line is checked against the generic/default standard,
    etc.) — case-insensitive substring match against `keyword`.

    Standards are configurable rows, not hardcoded — see
    app/rules/font_size_standards.yaml and the /font-size/standards API,
    which mirrors the same dynamic-rule pattern as rule_engine.py.
    """
    results = []
    default_standards = [s for s in standards if s.get("keyword") in (None, "", "DEFAULT")]
    keyworded_standards = [s for s in standards if s.get("keyword") not in (None, "", "DEFAULT")]

    for m in measurements:
        text_lower = m.text.lower()
        matched = next(
            (s for s in keyworded_standards if s["keyword"].lower() in text_lower),
            None,
        )
        standard = matched or (default_standards[0] if default_standards else None)
        if standard is None:
            results.append(
                {
                    "text": m.text,
                    "heightPx": m.height_px,
                    "heightMm": m.height_mm,
                    "requiredMm": None,
                    "standardName": None,
                    "status": "REVIEW",
                    "note": "No configured font-size standard matched this text — nothing to compare against.",
                }
            )
            continue
        required_mm = standard["min_height_mm"]
        status = "PASS" if m.height_mm >= required_mm else "FAIL"
        results.append(
            {
                "text": m.text,
                "heightPx": m.height_px,
                "heightMm": m.height_mm,
                "requiredMm": required_mm,
                "standardName": standard["name"],
                "status": status,
                "note": standard.get("source", ""),
            }
        )
    return results
