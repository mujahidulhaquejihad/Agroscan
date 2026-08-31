"""Robust image loading for mixed formats (JPEG, PNG, WebP, GIF, TIFF, etc.)."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import BinaryIO, List, Union

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError


def openable_path(path: Union[str, Path]) -> str:
    """Absolute path that ``open()`` can use on Windows even past MAX_PATH (260)."""
    p = os.path.abspath(os.fspath(path))
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        if p.startswith("\\\\"):
            return "\\\\?\\UNC\\" + p.lstrip("\\")
        return "\\\\?\\" + p
    return p

# Allow slightly truncated JPEGs instead of failing the whole training step.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Training crops to ~224–300px. Decode larger than this wastes RAM
# (phone photos from BD leaf datasets are often 3000–4000px).
MAX_DECODE_SIDE = 1024

IMG_EXTS = {
    ".jpg",
    ".jpeg",
    ".jpe",
    ".jfif",
    ".png",
    ".bmp",
    ".webp",
    ".gif",
    ".tif",
    ".tiff",
}

# Never treat these as images even if a folder contains them.
SKIP_EXTS = {
    ".lnk",
    ".txt",
    ".csv",
    ".json",
    ".md",
    ".xml",
    ".html",
    ".zip",
    ".py",
    ".yaml",
    ".yml",
    ".db",
    ".pt",
    ".pth",
    ".onnx",
}

_MAGIC = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"RIFF", "webp"),  # WEBP: RIFF....WEBP
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
)


def _downscale_if_needed(img: Image.Image, max_side: int = MAX_DECODE_SIDE) -> Image.Image:
    """Shrink huge images before RGB conversion / EXIF rotate."""
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    img = img.copy()
    img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    return img


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert any PIL mode to RGB (handles RGBA, palette, grayscale, CMYK)."""
    img = _downscale_if_needed(img)
    try:
        img = ImageOps.exif_transpose(img) or img
    except Exception:
        pass
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def load_rgb_image(
    source: Union[str, Path, bytes, bytearray, BinaryIO, Image.Image],
    *,
    fallback_size: int | None = 224,
) -> Image.Image:
    """Open an image from a path, bytes buffer, or existing PIL image -> RGB."""
    try:
        if isinstance(source, Image.Image):
            return _to_rgb(source)

        if isinstance(source, (bytes, bytearray)):
            with Image.open(io.BytesIO(source)) as img:
                try:
                    img.draft("RGB", (MAX_DECODE_SIDE, MAX_DECODE_SIDE))
                except Exception:
                    pass
                img.load()
                return _to_rgb(img)

        if isinstance(source, (str, Path)):
            with open(openable_path(source), "rb") as f:
                with Image.open(f) as img:
                    try:
                        img.draft("RGB", (MAX_DECODE_SIDE, MAX_DECODE_SIDE))
                    except Exception:
                        pass
                    img.load()
                    return _to_rgb(img)

        with Image.open(source) as img:
            try:
                img.draft("RGB", (MAX_DECODE_SIDE, MAX_DECODE_SIDE))
            except Exception:
                pass
            img.load()
            return _to_rgb(img)

    except (OSError, UnidentifiedImageError, ValueError, SyntaxError, MemoryError):
        if fallback_size is None:
            raise
        return Image.new("RGB", (fallback_size, fallback_size), (128, 128, 128))


def sniff_image_path(path: Path) -> bool:
    """True if file header looks like a supported raster image."""
    try:
        with open(openable_path(path), "rb") as f:
            header = f.read(16)
    except OSError:
        return False
    if not header:
        return False
    for magic, kind in _MAGIC:
        if kind == "webp":
            if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
                return True
        elif header.startswith(magic):
            return True
    return False


def is_image_path(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in SKIP_EXTS:
        return False
    if ext in IMG_EXTS:
        return True
    if not ext:
        return sniff_image_path(path)
    return False


def gather_images(folder: Path) -> List[Path]:
    """Collect image files under folder, including mixed extensions."""
    if not folder.exists():
        return []
    out: List[Path] = []
    for path in folder.rglob("*"):
        if path.is_file() and is_image_path(path):
            out.append(path)
    return out
