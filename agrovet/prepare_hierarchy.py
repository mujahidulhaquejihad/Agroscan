"""Merge duplicate labels (A), build leaf_type (F), relocate leaf_gate.

Run once after Datasets/{train,valid,test} exist:

    python -m agrovet.prepare_hierarchy
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import config
from .image_io import is_image_path
from .label_map import MERGE_ALIASES, crop_from_class, is_variety_class


def _unique_path(folder: Path, name: str) -> Path:
    dest = folder / name
    if not dest.exists():
        return dest
    stem, suf = dest.stem, dest.suffix
    i = 1
    while True:
        cand = folder / f"{stem}__m{i}{suf}"
        if not cand.exists():
            return cand
        i += 1


def _safe_name(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in text)[:80]


def _hardlink(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def _iter_images(folder: Path):
    for path in folder.rglob("*"):
        if path.is_file() and is_image_path(path):
            yield path


def merge_duplicate_labels() -> int:
    """Move alias class folders onto their canonical names (A)."""
    moved = 0
    for split in ("train", "valid", "test"):
        root = config.DATASETS / split
        if not root.is_dir():
            continue
        for alias, canonical in MERGE_ALIASES.items():
            src = root / alias
            dst = root / canonical
            if not src.is_dir():
                continue
            dst.mkdir(parents=True, exist_ok=True)
            for path in list(_iter_images(src)):
                dest = _unique_path(dst, path.name)
                try:
                    if dest.exists() and os.path.samefile(path, dest):
                        path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                os.replace(path, dest)
                moved += 1
            leftover = list(_iter_images(src))
            if leftover:
                print(f"  leftover files in {src}: {len(leftover)}")
            else:
                shutil.rmtree(src, ignore_errors=True)
                print(f"  merged {split}/{alias} -> {canonical}")
    return moved


def build_leaf_type() -> int:
    """Hard-link every disease image into Datasets/leaf_type/{split}/{Crop}/."""
    if config._split_has_classes(config.CROP_TRAIN):
        print(f"  leaf_type already at {config.CROP_DIR}")
        return 0
    linked = 0
    dest_root = config.CROP_DIR
    for split in ("train", "valid", "test"):
        src_root = config.DATASETS / split
        if not src_root.is_dir():
            continue
        n_split = 0
        for class_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
            crop = crop_from_class(class_dir.name)
            out = dest_root / split / crop
            prefix = _safe_name(class_dir.name)[:12]
            for i, path in enumerate(_iter_images(class_dir), 1):
                dest = out / f"{prefix}_{i:08d}{path.suffix.lower()}"
                if dest.exists():
                    continue
                _hardlink(path, dest)
                linked += 1
                n_split += 1
        print(f"  leaf_type/{split}: {n_split:,} images")
    return linked


def drop_variety_from_disease() -> int:
    """Keep mango variety images in leaf_type only; drop them from Level 3."""
    removed = 0
    for split in ("train", "valid", "test"):
        root = config.DATASETS / split
        if not root.is_dir():
            continue
        for class_dir in list(p for p in root.iterdir() if p.is_dir()):
            if not is_variety_class(class_dir.name):
                continue
            n = sum(1 for _ in _iter_images(class_dir))
            shutil.rmtree(class_dir, ignore_errors=True)
            removed += n
            print(f"  dropped Level-3 variety {split}/{class_dir.name} ({n} files)")
    return removed


def relocate_leaf_gate() -> None:
    src = config.VISION / "leaf_gate"
    dst = config.LEAF_GATE_DIR
    if dst.is_dir() and any(dst.iterdir()):
        print(f"  leaf_gate already at {dst}")
        if src.is_dir() and src.resolve() != dst.resolve():
            shutil.rmtree(src, ignore_errors=True)
        return
    if src.is_dir():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"  moved {src} -> {dst}")
    else:
        print(f"  no leaf_gate at {src}")


def main() -> None:
    print("=== A: merge duplicate disease labels ===")
    n = merge_duplicate_labels()
    print(f"Moved {n:,} files into canonical class folders.")

    print("\n=== F: build Datasets/leaf_type ===")
    n = build_leaf_type()
    print(f"Hard-linked {n:,} images into leaf_type.")

    print("\n=== Drop mango variety folders from Level-3 splits ===")
    n = drop_variety_from_disease()
    print(f"Removed {n:,} variety files from disease splits.")

    print("\n=== Relocate leaf_gate to Datasets/leaf_gate ===")
    relocate_leaf_gate()
    print("Done.")


if __name__ == "__main__":
    main()
