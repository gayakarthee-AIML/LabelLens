"""
YOLO region detection.

Locates candidate label/declaration regions (front label block, barcode
block, fine-print block) inside a package photo before OCR runs, so
PaddleOCR is pointed at the right crops instead of running blind on the
whole frame — this is what the "YOLO region detection" step in the pipeline
diagram refers to.

Training a custom label-region YOLO model is outside what can be produced in
this environment (no GPU, no dataset, no network to pull pretrained weights).
This module is written against the real `ultralytics` inference API — drop a
trained `label_regions.pt` at YOLO_WEIGHTS_PATH and it runs unmodified. Until
a weights file is present, `detect_regions` degrades to a single full-frame
region so the rest of the pipeline (OCR, declaration extraction, rules) keeps
working end-to-end rather than raising or fabricating detections.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import get_settings

settings = get_settings()

_model = None
_model_load_attempted = False


@dataclass
class Region:
    label: str  # e.g. "label_block", "barcode_block", "fine_print"
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


def _get_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    weights_path = Path(settings.yolo_weights_path)
    if not weights_path.exists():
        return None
    try:
        from ultralytics import YOLO  # imported lazily — heavy dependency

        _model = YOLO(str(weights_path))
    except Exception:
        _model = None
    return _model


def detect_regions(image: np.ndarray, conf_threshold: float = 0.35) -> list[Region]:
    model = _get_model()
    h, w = image.shape[:2]

    if model is None:
        # No trained weights available in this environment — treat the whole
        # frame as one region rather than inventing bounding boxes.
        return [Region(label="full_frame", confidence=1.0, x1=0, y1=0, x2=w, y2=h)]

    results = model.predict(source=image, conf=conf_threshold, verbose=False)
    regions: list[Region] = []
    for result in results:
        names = result.names
        for box in result.boxes:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            cls_id = int(box.cls[0].item())
            regions.append(
                Region(
                    label=names.get(cls_id, str(cls_id)),
                    confidence=float(box.conf[0].item()),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
    if not regions:
        regions.append(Region(label="full_frame", confidence=1.0, x1=0, y1=0, x2=w, y2=h))
    return regions
