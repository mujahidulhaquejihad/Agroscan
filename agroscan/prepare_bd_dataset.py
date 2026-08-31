"""Download Bangladesh crop disease dataset from Hugging Face to Datasets/vision/disease/.

Usage (from project root):

    python -m pip install datasets huggingface_hub
    huggingface-cli login          # after accepting terms on the Hub page
    python -m agroscan.prepare_bd_dataset info
    python -m agroscan.prepare_bd_dataset download

The dataset is gated:
https://huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .bd_dataset import (
    bd_split_stats,
    export_to_imagefolder,
    hf_access_help,
    hf_repo_id,
    load_bd_splits,
    print_dataset_info,
)


def _write_manifest(out_dir: Path) -> None:
    ds = load_bd_splits()
    names = list(ds["train"].features["label"].names)
    manifest = {
        "hub_repo": hf_repo_id(),
        "num_classes": len(names),
        "class_names": names,
        "splits": {split: len(ds[split]) for split in ds.keys()},
        "export_dir": str(out_dir),
    }
    path = out_dir / "dataset_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def main():
    ap = argparse.ArgumentParser(description="Bangladesh crop disease dataset (Hugging Face)")
    ap.add_argument(
        "command",
        choices=("info", "download"),
        help="info = print stats; download = export to Datasets/vision/disease/bd_crop_disease/",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=config.BD_EXPORT_DIR,
        help=f"Output folder (default: {config.BD_EXPORT_DIR})",
    )
    ap.add_argument(
        "--max-per-class",
        type=int,
        default=None,
        help="Optional cap per class (for quick tests only)",
    )
    args = ap.parse_args()

    if args.command == "info":
        try:
            print_dataset_info()
        except PermissionError as e:
            print(e)
            raise SystemExit(1)
        return

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Downloading from Hugging Face: {hf_repo_id()}")
    print(f"Export target: {out.resolve()}")
    print("This is ~123k images — expect a long download and 15–40 GB disk use.\n")

    try:
        stats = bd_split_stats()
        print("Hub splits:", stats)
        export_to_imagefolder(
            out,
            splits=("train", "valid", "test"),
            max_per_class=args.max_per_class,
        )
        _write_manifest(out)
        print("\nDownload complete.")
        print(f"  train/  -> {out / 'train'}")
        print(f"  valid/  -> {out / 'valid'}")
        print(f"  test/   -> {out / 'test'}")
    except PermissionError as e:
        print(e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
