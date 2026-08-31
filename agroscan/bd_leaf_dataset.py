"""Bangladeshi Leaf Disease Detection Dataset (local zip -> ImageFolder)."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional

from . import config
from .image_io import gather_images, is_image_path

ZIP_NAME = "Leaf Disease detection Dataset.zip"
INNER_ROOT = "Leaf Disease detection Dataset"


def find_bd_leaf_zip() -> Optional[Path]:
    """Locate the dataset zip under Datasets/ (supports nested download folders)."""
    if config.BD_LEAF_ZIP.exists():
        return config.BD_LEAF_ZIP
    matches = sorted(config.BD_LEAF_DATASET_DIR.rglob(ZIP_NAME))
    return matches[0] if matches else None


def is_bd_leaf_extracted() -> bool:
    root = config.BD_LEAF_EXPORT_DIR
    if not root.exists():
        return False
    class_dirs = [p for p in root.iterdir() if p.is_dir()]
    if not class_dirs:
        return False
    return any(gather_images(class_dirs[0]))


def ensure_bd_leaf_extracted(*, force: bool = False) -> Path:
    """Extract the zip to Datasets/vision/disease/bd_leaf_disease/ if not already present."""
    out = config.BD_LEAF_EXPORT_DIR
    if not force and is_bd_leaf_extracted():
        return out

    zpath = find_bd_leaf_zip()
    if zpath is None:
        raise FileNotFoundError(
            f"Could not find {ZIP_NAME!r} under {config.BD_LEAF_DATASET_DIR}. "
            "Add the Bangladeshi Leaf Disease Detection Dataset folder to Datasets/sources/."
        )

    out.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {zpath.name} ({zpath.stat().st_size / 1e9:.1f} GB) -> {out}")
    print("This runs once; later training reuses the extracted images.\n")

    with zipfile.ZipFile(zpath) as zf:
        members = [
            m for m in zf.namelist()
            if m.startswith(f"{INNER_ROOT}/")
            and not m.endswith("/")
            and is_image_path(Path(m.split("/")[-1]))
        ]
        try:
            from tqdm import tqdm
            iterator = tqdm(members, desc="extract", unit="img")
        except ImportError:
            iterator = members

        for member in iterator:
            parts = [p for p in member.split("/") if p]
            if len(parts) < 3:
                continue
            class_name = parts[1]
            filename = parts[-1]
            dest = out / class_name / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and not force:
                continue
            with zf.open(member) as src, dest.open("wb") as dst:
                dst.write(src.read())

    n_images = sum(len(gather_images(p)) for p in out.iterdir() if p.is_dir())
    print(f"Extracted {n_images:,} images to {out.resolve()}")
    return out


def bd_leaf_stats() -> dict:
    root = config.BD_LEAF_EXPORT_DIR
    if not root.exists():
        return {}
    stats = {}
    for class_dir in sorted(root.iterdir()):
        if class_dir.is_dir():
            stats[class_dir.name] = len(gather_images(class_dir))
    return stats
