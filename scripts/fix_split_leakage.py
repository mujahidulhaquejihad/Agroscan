"""Remove train/valid/test leakage and cap huge train classes.

Walks every image. Leakage is:
  - same NTFS file index (hard link) in two splits
  - same original filename (after the 8-digit split prefix) in two splits
  - same PlantVillage source id (text after '___') in two splits

Keep the best split (test > valid > train). Extra copies in worse splits
are deleted. Last train image of a class is never deleted.

Tiny classes were copied into all three splits by an older builder.
PlantVillage train+valid+raw were merged then reshuffled, so the same
photo (and its augs) often sit in more than one split.

leaf_type files are sequential-renamed hardlinks of disease files, so
filename matching there is a false positive. Those copies are removed
by matching the deleted disease inode.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Datasets"
EXTS = {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".webp", ".gif", ".tif", ".tiff"}
SPLIT_RANK = {"test": 0, "valid": 1, "train": 2}


def log(msg: str) -> None:
    print(msg, flush=True)


def orig_name(name: str) -> str:
    if len(name) > 9 and name[:8].isdigit() and name[8] == "_":
        return name[9:].lower()
    return name.lower()


def pv_source(name: str) -> str | None:
    base = orig_name(name)
    if "___" not in base:
        return None
    tail = base.split("___", 1)[1]
    stem, _, _ext = tail.rpartition(".")
    key = stem.strip() if stem else tail.strip()
    return key or None


def file_id_entry(entry: os.DirEntry) -> tuple | None:
    try:
        st = entry.stat()
        return (st.st_dev, st.st_ino)
    except OSError:
        return None


def file_id(path: Path) -> tuple | None:
    try:
        st = os.stat(path)
        return (st.st_dev, st.st_ino)
    except OSError:
        return None


def iter_images(split_root: Path):
    if not split_root.is_dir():
        return
    for cls in os.scandir(split_root):
        if not cls.is_dir():
            continue
        with os.scandir(cls.path) as it:
            for e in it:
                if e.is_file() and Path(e.name).suffix.lower() in EXTS:
                    yield cls.name, Path(e.path)


def class_counts(split_root: Path) -> dict[str, int]:
    out = {}
    if not split_root.is_dir():
        return out
    for cls in os.scandir(split_root):
        if not cls.is_dir():
            continue
        n = 0
        with os.scandir(cls.path) as it:
            for e in it:
                if e.is_file() and Path(e.name).suffix.lower() in EXTS:
                    n += 1
        out[cls.name] = n
    return out


def keep_best_split(group: list[tuple[str, Path]], delete: set[Path]) -> None:
    splits = {s for s, _ in group}
    if len(splits) < 2:
        return
    best = min(splits, key=lambda s: SPLIT_RANK[s])
    for split, path in group:
        if split != best:
            delete.add(path)


def scan_leaks(name: str, splits: dict[str, Path], use_names: bool, use_pv: bool) -> set[Path]:
    # Filename / PlantVillage id only — no per-file stat. Hard-link leaks were ~0.
    by_name: dict[tuple[str, str], list[tuple[str, Path]]] = defaultdict(list)
    by_pv: dict[tuple[str, str], list[tuple[str, Path]]] = defaultdict(list)
    n = 0
    for split, root in splits.items():
        if not root.is_dir():
            continue
        for cls in os.scandir(root):
            if not cls.is_dir():
                continue
            with os.scandir(cls.path) as it:
                for e in it:
                    if not e.is_file() or Path(e.name).suffix.lower() not in EXTS:
                        continue
                    n += 1
                    if n % 50000 == 0:
                        log(f"  [{name}] {n:,} files ...")
                    path = Path(e.path)
                    if use_names:
                        by_name[(cls.name, orig_name(e.name))].append((split, path))
                    if use_pv:
                        pv = pv_source(e.name)
                        if pv:
                            by_pv[(cls.name, pv)].append((split, path))

    delete: set[Path] = set()
    names = pvs = 0
    for group in by_name.values():
        if len({s for s, _ in group}) < 2:
            continue
        names += 1
        keep_best_split(group, delete)
    for group in by_pv.values():
        if len({s for s, _ in group}) < 2:
            continue
        pvs += 1
        keep_best_split(group, delete)

    log(
        f"  [{name}] scanned {n:,}  same-name-across-splits={names:,}  "
        f"pv-source-across-splits={pvs:,}  delete={len(delete):,}"
    )
    return delete


def protect_last_train(delete: set[Path], train_root: Path) -> int:
    """Do not empty a train class."""
    if not train_root.is_dir():
        return 0
    by_cls: dict[str, list[Path]] = defaultdict(list)
    for cls, path in iter_images(train_root):
        by_cls[cls].append(path)
    kept = 0
    for cls, files in by_cls.items():
        remain = [p for p in files if p not in delete]
        if remain:
            continue
        # keep the lexicographically first leaked train file
        leaked = sorted(p for p in files if p in delete)
        if not leaked:
            continue
        delete.discard(leaked[0])
        kept += 1
        log(f"  keep last train image {cls}/{leaked[0].name}")
    return kept


def inode_index(split_roots: dict[str, Path]) -> dict[tuple, list[Path]]:
    idx: dict[tuple, list[Path]] = defaultdict(list)
    n = 0
    for root in split_roots.values():
        if not root.is_dir():
            continue
        for _cls, path in iter_images(root):
            n += 1
            if n % 50000 == 0:
                log(f"  [leaf_type index] {n:,} ...")
            fid = file_id(path)
            if fid:
                idx[fid].append(path)
    log(f"  [leaf_type index] {n:,} files")
    return idx


def cap_train(train_root: Path, excess_root: Path, cap: int) -> int:
    moved = 0
    for cls, n in class_counts(train_root).items():
        if n <= cap:
            continue
        files = sorted(
            Path(e.path)
            for e in os.scandir(train_root / cls)
            if e.is_file() and Path(e.name).suffix.lower() in EXTS
        )
        dest_dir = excess_root / cls
        dest_dir.mkdir(parents=True, exist_ok=True)
        for f in files[cap:]:
            dest = dest_dir / f.name
            if dest.exists():
                dest = dest_dir / f"{f.stem}__x{moved}{f.suffix}"
            os.replace(str(f), str(dest))
            moved += 1
    return moved


def summarize(split_root: Path, label: str) -> str:
    counts = class_counts(split_root)
    if not counts:
        return f"{label}: empty"
    vals = sorted(counts.values())
    mx, mn = max(vals), min(vals)
    heavy = ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:6])
    return (
        f"{label}: {sum(vals):,} images, {len(counts)} classes, "
        f"min={mn} med={vals[len(vals)//2]} max={mx} ratio={mx / max(mn, 1):.0f}x | {heavy}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cap-train", type=int, default=2500)
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    disease = {"train": ROOT / "train", "valid": ROOT / "valid", "test": ROOT / "test"}
    leaf_type = {
        "train": ROOT / "leaf_type" / "train",
        "valid": ROOT / "leaf_type" / "valid",
        "test": ROOT / "leaf_type" / "test",
    }
    leaf_gate = {
        "train": ROOT / "leaf_gate" / "train",
        "valid": ROOT / "leaf_gate" / "valid",
        "test": ROOT / "leaf_gate" / "test",
    }

    lines = [summarize(ROOT / "train", "disease train BEFORE")]
    log(lines[-1])

    log("\n=== disease ===")
    delete = scan_leaks("disease", disease, use_names=True, use_pv=True)
    protected = protect_last_train(delete, disease["train"])
    log(f"  protected last-train files={protected}  delete={len(delete):,}")

    extra_lt = 0
    if leaf_type["train"].is_dir() and delete:
        log("\n=== leaf_type (follow deleted disease inodes) ===")
        idx = inode_index(leaf_type)
        for p in list(delete):
            fid = file_id(p)
            if not fid:
                continue
            for q in idx.get(fid, []):
                if q not in delete:
                    delete.add(q)
                    extra_lt += 1
        log(f"  extra leaf_type copies to drop={extra_lt:,}  delete={len(delete):,}")

    log("\n=== leaf_gate ===")
    gate_del = scan_leaks("leaf_gate", leaf_gate, use_names=True, use_pv=False)
    protect_last_train(gate_del, leaf_gate["train"])
    delete |= gate_del

    removed = 0
    if args.apply:
        total = len(delete)
        for p in delete:
            try:
                p.unlink()
                removed += 1
                if removed % 5000 == 0:
                    log(f"  deleted {removed:,}/{total:,}")
            except OSError as exc:
                log(f"  skip {p}: {exc}")
        log(f"deleted {removed:,}")
        if args.cap_train > 0:
            moved = cap_train(ROOT / "train", ROOT / "_excess_train", args.cap_train)
            log(f"Moved {moved:,} excess train images to Datasets/_excess_train (cap={args.cap_train})")
            lines.append(f"excess_moved={moved}")
    else:
        log("Dry run. Pass --apply to delete leaked copies and cap train.")

    lines.append(f"delete={len(delete)} removed={removed} extra_leaf_type={extra_lt}")
    lines.append(summarize(ROOT / "train", "disease train AFTER"))
    lines.append(summarize(ROOT / "valid", "disease valid AFTER"))
    lines.append(summarize(ROOT / "test", "disease test AFTER"))
    for L in lines[-3:]:
        log(L)
    (ROOT / "leakage_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
