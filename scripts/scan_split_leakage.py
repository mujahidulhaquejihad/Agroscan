"""Fast leakage inventory: filenames, PlantVillage source ids, hardlinks.

Does not delete. Prints counts and writes Datasets/leakage_scan.txt.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Datasets"
EXTS = {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".webp", ".gif", ".tif", ".tiff"}
SPLITS = ("train", "valid", "test")


def log(msg: str) -> None:
    print(msg, flush=True)


def orig_name(name: str) -> str:
    if len(name) > 9 and name[:8].isdigit() and name[8] == "_":
        return name[9:].lower()
    return name.lower()


def pv_source(name: str) -> str | None:
    """PlantVillage original id after '___' (shared by augs of the same photo)."""
    base = orig_name(name)
    if "___" not in base:
        return None
    tail = base.split("___", 1)[1]
    stem, _, _ext = tail.rpartition(".")
    key = stem.strip() if stem else tail.strip()
    return key or None


def scan_task(name: str, split_roots: dict[str, Path], use_names: bool = True) -> dict:
    by_name: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_pv: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_ino: dict[tuple, set[str]] = defaultdict(set)
    n = 0
    for split, root in split_roots.items():
        if not root.is_dir():
            continue
        for clsdir in os.scandir(root):
            if not clsdir.is_dir():
                continue
            cls = clsdir.name
            with os.scandir(clsdir.path) as it:
                for e in it:
                    if not e.is_file():
                        continue
                    suf = Path(e.name).suffix.lower()
                    if suf not in EXTS:
                        continue
                    n += 1
                    if n % 50000 == 0:
                        log(f"  [{name}] {n:,} ...")
                    if use_names:
                        on = orig_name(e.name)
                        by_name[(cls, on)].add(split)
                    pv = pv_source(e.name)
                    if pv:
                        by_pv[(cls, pv)].add(split)
                    try:
                        # DirEntry.stat() on Windows reports st_ino=0; os.stat is real.
                        st = os.stat(e.path)
                        if st.st_ino:
                            by_ino[(st.st_dev, st.st_ino)].add(split)
                    except OSError:
                        pass
    name_leak = sum(1 for s in by_name.values() if len(s) > 1)
    pv_leak = sum(1 for s in by_pv.values() if len(s) > 1)
    ino_leak = sum(1 for s in by_ino.values() if len(s) > 1)
    log(
        f"  [{name}] files={n:,}  same-filename-across-splits={name_leak:,}  "
        f"pv-source-across-splits={pv_leak:,}  hardlink-across-splits={ino_leak:,}"
    )
    # examples
    ex_name = [(k, sorted(v)) for k, v in by_name.items() if len(v) > 1][:5]
    ex_pv = [(k, sorted(v)) for k, v in by_pv.items() if len(v) > 1][:5]
    for item in ex_name:
        log(f"    name ex {item}")
    for item in ex_pv:
        log(f"    pv   ex {item}")
    return {
        "files": n,
        "name_leak": name_leak,
        "pv_leak": pv_leak,
        "ino_leak": ino_leak,
        "pv_groups": len(by_pv),
    }


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    tasks = {
        "disease": {
            "train": ROOT / "train",
            "valid": ROOT / "valid",
            "test": ROOT / "test",
        },
        # leaf_type files are sequential-renamed; filename match is a false positive.
        # Disease cleanup already dropped the matching hardlinks.
        "leaf_type": {
            "train": ROOT / "leaf_type" / "train",
            "valid": ROOT / "leaf_type" / "valid",
            "test": ROOT / "leaf_type" / "test",
        },
        "leaf_gate": {
            "train": ROOT / "leaf_gate" / "train",
            "valid": ROOT / "leaf_gate" / "valid",
            "test": ROOT / "leaf_gate" / "test",
        },
    }
    lines = []
    for name, splits in tasks.items():
        if not splits["train"].is_dir():
            log(f"skip {name}: no train dir")
            continue
        log(f"=== {name} ===")
        st = scan_task(name, splits, use_names=(name != "leaf_type"))
        lines.append(f"{name}: {st}")
    out = ROOT / "leakage_scan.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote {out}")


if __name__ == "__main__":
    main()
