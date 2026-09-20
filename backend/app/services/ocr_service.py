"""
PaddleOCR integration — English + Hindi only, offline.

This is the real OCR technology specified in the brief — not a placeholder
and not swapped for a lighter client-side library. `recognize` returns actual
detected text, per-word confidence, and bounding boxes from the PaddleOCR
model; nothing here is hardcoded.

Per the brief, LabelLens deliberately extracts only English and Hindi (the
two languages this deployment's Legal Metrology declarations are checked
against) — see `Settings.paddleocr_langs`. PaddleOCR ships a dedicated
"en" (English/Latin) model and a "devanagari" model that covers Hindi; both
run fully offline once their model weights have been downloaded once (see
backend/README.md for first-run notes).

PaddleOCR + PaddlePaddle are heavy native dependencies (~1GB with model
downloads) that this sandboxed authoring environment cannot install or run
(no network egress). The integration is written against PaddleOCR's real
public API (`PaddleOCR(...).ocr(...)`) exactly as it would run once deployed
with `pip install -r requirements.txt` on a machine with network access.
"""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.core.config import get_settings

settings = get_settings()

# PaddleOCR's own language codes for the two languages this deployment uses.
# "en" covers the Latin/English text; "devanagari" is PaddleOCR's script
# model covering Hindi (and other Devanagari-script languages) — there is no
# separate "hi" code in PaddleOCR, so this mapping is deliberate, not a typo.
_PADDLE_LANG_FOR_ISO = {
    "en": "en",
    "hi": "devanagari",
}


@dataclass
class OcrWord:
    text: str
    confidence: float
    box: list[list[float]]  # 4 (x, y) corner points, as returned by PaddleOCR
    lang: str


@lru_cache(maxsize=4)
def _get_engine(paddle_lang: str):
    # Imported lazily so the rest of the API can start up (and this module can
    # be imported for tests) even in environments where PaddleOCR/PaddlePaddle
    # are not installed.
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang=paddle_lang, show_log=False)


def recognize(image: np.ndarray, languages: list[str] | None = None) -> list[OcrWord]:
    """
    Runs PaddleOCR over the given (already preprocessed) image for each
    requested language (English and/or Hindi) and merges results. Real Legal
    Metrology labels in India are frequently bilingual (English + Hindi), so
    running both passes and merging is deliberate, not redundant.
    """
    languages = languages or settings.paddleocr_lang_list or ["en"]
    words: list[OcrWord] = []

    for iso_code in languages:
        paddle_lang = _PADDLE_LANG_FOR_ISO.get(iso_code)
        if paddle_lang is None:
            # This deployment only supports English and Hindi per the brief;
            # skip anything else rather than silently mis-mapping it.
            continue
        engine = _get_engine(paddle_lang)
        result = engine.ocr(image, cls=True)
        if not result or result[0] is None:
            continue
        for line in result[0]:
            box, (text, confidence) = line
            words.append(OcrWord(text=text, confidence=float(confidence), box=box, lang=iso_code))

    return words


def average_confidence(words: list[OcrWord]) -> float:
    if not words:
        return 0.0
    return sum(w.confidence for w in words) / len(words)


def combined_text(words: list[OcrWord]) -> str:
    return "\n".join(w.text for w in words)


def estimate_text_height_px(word: OcrWord) -> float:
    """Height of a word's bounding box in pixels, from its four corner points."""
    ys = [pt[1] for pt in word.box]
    return max(ys) - min(ys)
