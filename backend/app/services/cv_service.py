"""
OpenCV preprocessing pipeline.

Camera / Upload -> validate -> resize -> denoise -> contrast enhance ->
perspective correction -> blur/brightness/glare analysis -> (handed off to
yolo_service for region detection, then ocr_service for text extraction).

Every function here operates on real pixel data (numpy arrays from cv2) —
there is no branch that returns a canned number.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class QualityReport:
    brightness: float
    blur_score: float
    glare_pct: float
    flags: list[str] = field(default_factory=list)


def load_image(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image — file may be corrupt or an unsupported format.")
    return image


def resize_max_dim(image: np.ndarray, max_dim: int = 2000) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(1.0, max_dim / max(h, w))
    if scale < 1.0:
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return image


def denoise(image: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    merged = cv2.merge((l, a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def correct_perspective(image: np.ndarray) -> np.ndarray:
    """
    Attempts to find the largest quadrilateral contour (the label/package edge)
    and warps it to a front-on rectangle. Falls back to the original image if
    no confident quadrilateral is found — this is a best-effort step, not a
    guaranteed correction, and never fabricates a warp.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 0.2 * image.shape[0] * image.shape[1]:
        return image  # too small to be confident this is the package outline

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        return image

    pts = approx.reshape(4, 2).astype("float32")
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    if max_width < 50 or max_height < 50:
        return image

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def analyze_quality(image: np.ndarray) -> QualityReport:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    glare_pct = float(np.mean(gray > 245))

    flags = []
    if brightness < 60:
        flags.append("LOW_BRIGHTNESS")
    elif brightness > 220:
        flags.append("OVEREXPOSED")
    if blur_score < 60:  # threshold tuned for full-resolution images (higher than the client preview's)
        flags.append("BLUR_DETECTED")
    if glare_pct > 0.12:
        flags.append("GLARE_DETECTED")

    return QualityReport(brightness=brightness, blur_score=blur_score, glare_pct=glare_pct, flags=flags)


def preprocess(image_bytes: bytes) -> tuple[np.ndarray, QualityReport]:
    """Full pipeline entry point used by the inspection image upload endpoint."""
    image = load_image(image_bytes)
    image = resize_max_dim(image)
    quality = analyze_quality(image)  # measured on the original — don't let denoise/CLAHE mask real issues
    image = denoise(image)
    image = enhance_contrast(image)
    image = correct_perspective(image)
    return image, quality


def encode_jpeg(image: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Failed to encode processed image")
    return buf.tobytes()
