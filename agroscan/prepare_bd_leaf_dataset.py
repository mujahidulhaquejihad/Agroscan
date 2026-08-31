"""Extract Bangladeshi Leaf Disease Detection Dataset zip to Datasets/vision/disease/bd_leaf_disease/.

Usage (from project root):

    python -m agroscan.prepare_bd_leaf_dataset
    python -m agroscan.prepare_bd_leaf_dataset info
"""
from __future__ import annotations

import argparse

from .bd_leaf_dataset import bd_leaf_stats, ensure_bd_leaf_extracted, find_bd_leaf_zip
from . import config


def main():
    ap = argparse.ArgumentParser(description="Bangladeshi Leaf Disease Detection Dataset")
    ap.add_argument(
        "command",
        nargs="?",
        default="extract",
        choices=("extract", "info"),
        help="extract = unzip to Datasets/vision/disease/bd_leaf_disease/; info = print status",
    )
    ap.add_argument("--force", action="store_true", help="Re-extract even if already present")
    args = ap.parse_args()

    if args.command == "info":
        zpath = find_bd_leaf_zip()
        print(f"Zip: {zpath or 'NOT FOUND'}")
        print(f"Export dir: {config.BD_LEAF_EXPORT_DIR}")
        stats = bd_leaf_stats()
        if stats:
            print("Classes:")
            for name, count in stats.items():
                print(f"  {name}: {count:,}")
            print(f"Total: {sum(stats.values()):,}")
        else:
            print("Not extracted yet. Run: python -m agroscan.prepare_bd_leaf_dataset extract")
        return

    ensure_bd_leaf_extracted(force=args.force)
    stats = bd_leaf_stats()
    print("Ready for training:", stats)


if __name__ == "__main__":
    main()
