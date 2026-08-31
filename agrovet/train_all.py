"""Orchestrate full training: leaf gate + crop type + disease ensemble."""
from __future__ import annotations

import argparse

from . import config
from .train_crop import train_crop
from .train_disease import train_one
from .train_leaf import train_leaf


def main():
    ap = argparse.ArgumentParser(description="Train all stages (supports --resume)")
    ap.add_argument("--skip-leaf", action="store_true")
    ap.add_argument("--skip-crop", action="store_true")
    ap.add_argument("--disease-source", default=config.DEFAULT_DISEASE_SOURCE, choices=("plantvillage", "bd", "combined"))
    ap.add_argument("--disease-epochs", type=int, default=config.DISEASE_EPOCHS)
    ap.add_argument("--disease-batch", type=int, default=config.DISEASE_BATCH)
    ap.add_argument("--resume", action="store_true", help="Resume each stage from its .train.pt snapshot")
    ap.add_argument("--ckpt-every", type=int, default=1, help="Extra epoch-tagged snapshots every N epochs")
    args = ap.parse_args()

    if not args.skip_leaf:
        print("########## LEVEL 1: LEAF GATE ##########")
        train_leaf(resume=args.resume, ckpt_every=args.ckpt_every)

    if not args.skip_crop:
        print("\n########## LEVEL 2: LEAF TYPE (CROP) ##########")
        train_crop(resume=args.resume, ckpt_every=args.ckpt_every)

    print("\n########## LEVEL 3: DISEASE ENSEMBLE ##########")
    results = {}
    for arch in config.DISEASE_ARCHS:
        results[arch] = train_one(
            arch, args.disease_epochs, args.disease_batch, config.DISEASE_LR,
            source=args.disease_source,
            resume=args.resume,
            ckpt_every=args.ckpt_every,
        )

    print("\n========== SUMMARY ==========")
    for arch, acc in results.items():
        print(f"{arch:>22}: best val_acc = {acc:.4f}")


if __name__ == "__main__":
    main()
