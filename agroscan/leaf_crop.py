"""Leaf image preprocessing: auto-crop and perspective crop from 4 corners.

Uses HSV + excess-green heuristics (works for healthy and diseased leaves)
and optional GrabCut refine when OpenCV is available. No heavy NN required.
"""
from __future__ import annotations

import io
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


def _pil_to_bgr(img: Image.Image) -> np.ndarray:
    rgb = np.array(img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _leaf_mask(bgr: np.ndarray) -> np.ndarray:
    """Binary mask of likely leaf pixels (green + yellow/brown disease tones)."""
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Healthy greens
    green = cv2.inRange(hsv, (25, 25, 25), (95, 255, 255))
    # Yellow / chlorosis
    yellow = cv2.inRange(hsv, (15, 30, 40), (35, 255, 255))
    # Brown spots / blight (low sat / mid value)
    brown = cv2.inRange(hsv, (5, 20, 20), (25, 200, 180))

    b, g, r = cv2.split(bgr.astype(np.int16))
    excess_green = (2 * g - r - b)
    eg = np.clip(excess_green, 0, 255).astype(np.uint8)
    _, eg_mask = cv2.threshold(eg, 18, 255, cv2.THRESH_BINARY)

    mask = cv2.bitwise_or(green, yellow)
    mask = cv2.bitwise_or(mask, brown)
    mask = cv2.bitwise_or(mask, eg_mask)

    # Drop very bright near-white background
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    bg = ((v > 210) & (s < 40)).astype(np.uint8) * 255
    mask = cv2.bitwise_and(mask, cv2.bitwise_not(bg))

    k = max(5, int(round(min(h, w) * 0.012)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def _largest_contour(mask: np.ndarray):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    return max(cnts, key=cv2.contourArea)


def _refine_grabcut(bgr: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """Optional GrabCut refine inside bbox. Returns mask or None."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    if w < 32 or h < 32:
        return None
    try:
        gc_mask = np.zeros(bgr.shape[:2], np.uint8)
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        rect = (x0, y0, w, h)
        cv2.grabCut(bgr, gc_mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
        return np.where((gc_mask == 2) | (gc_mask == 0), 0, 255).astype("uint8")
    except Exception:
        return None


def auto_crop_leaf(
    img: Image.Image,
    padding: float = 0.06,
    *,
    isolate: bool = False,
) -> Tuple[Image.Image, dict]:
    """Detect the main leaf region and return a tight crop.

    Works for green leaves and common disease colors (yellow/brown spots).
    """
    meta: dict = {"method": "auto", "found": False}
    if cv2 is None:
        meta["note"] = "opencv not installed"
        return img, meta

    bgr = _pil_to_bgr(img)
    h, w = bgr.shape[:2]
    mask = _leaf_mask(bgr)
    c = _largest_contour(mask)
    if c is None:
        meta["note"] = "no leaf contour"
        return img, meta

    area = float(cv2.contourArea(c))
    if area < 0.015 * h * w:
        meta["note"] = "contour too small"
        return img, meta

    x, y, bw, bh = cv2.boundingRect(c)
    pad_x = int(bw * padding)
    pad_y = int(bh * padding)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(w, x + bw + pad_x)
    y1 = min(h, y + bh + pad_y)

    refined = _refine_grabcut(bgr, (x0, y0, x1, y1))
    if refined is not None:
        c2 = _largest_contour(refined)
        if c2 is not None and cv2.contourArea(c2) > 0.01 * h * w:
            x, y, bw, bh = cv2.boundingRect(c2)
            pad_x = int(bw * padding)
            pad_y = int(bh * padding)
            x0 = max(0, x - pad_x)
            y0 = max(0, y - pad_y)
            x1 = min(w, x + bw + pad_x)
            y1 = min(h, y + bh + pad_y)
            meta["method"] = "auto+grabcut"
            mask = refined

    cropped = bgr[y0:y1, x0:x1].copy()
    if isolate:
        local = mask[y0:y1, x0:x1]
        # Soft white background outside leaf for cleaner model input
        white = np.full_like(cropped, 245)
        m3 = cv2.merge([local, local, local])
        cropped = np.where(m3 > 0, cropped, white)

    meta.update(
        {
            "found": True,
            "bbox": [int(x0), int(y0), int(x1), int(y1)],
            "area_ratio": round(area / (h * w), 4),
            "isolated": bool(isolate),
        }
    )
    return _bgr_to_pil(cropped), meta


def perspective_crop(
    img: Image.Image,
    points: List[List[float]],
    output_size: Optional[Tuple[int, int]] = None,
) -> Image.Image:
    """Crop quadrilateral defined by 4 points [[x,y], ...] in image pixel coords."""
    if cv2 is None or len(points) != 4:
        return img

    bgr = _pil_to_bgr(img)
    h, w = bgr.shape[:2]
    src = np.float32([[max(0, min(w, p[0])), max(0, min(h, p[1]))] for p in points])

    width_a = np.linalg.norm(src[2] - src[3])
    width_b = np.linalg.norm(src[1] - src[0])
    height_a = np.linalg.norm(src[1] - src[2])
    height_b = np.linalg.norm(src[0] - src[3])
    max_w = int(max(width_a, width_b))
    max_h = int(max(height_a, height_b))
    if max_w < 8 or max_h < 8:
        return img

    if output_size:
        max_w, max_h = output_size

    dst = np.float32([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]])
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(bgr, m, (max_w, max_h))
    return _bgr_to_pil(warped)


def image_to_jpeg_bytes(img: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
