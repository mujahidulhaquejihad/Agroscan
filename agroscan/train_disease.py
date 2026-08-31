"""Train a single Stage-2 disease classifier (one of the 3 ensemble members)."""
from __future__ import annotations

import argparse
import sys

import torch

from . import config
from .data import class_weights_for_dataset, disease_loaders
from .engine import train_model
from .models import build_model


def train_one(
    arch: str,
    epochs: int,
    batch: int,
    lr: float,
    source: str | None = None,
    *,
    resume: bool = False,
    ckpt_every: int = 1,
) -> float:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(config.SEED)
    size = config.INPUT_SIZE.get(arch, config.DEFAULT_INPUT_SIZE)
    src = source or config.DEFAULT_DISEASE_SOURCE

    print(f"\n=== Training disease model: {arch} (input={size}, device={device}, source={src}, resume={resume}) ===")
    train_dl, val_dl, class_names = disease_loaders(size, batch, source=src)
    print(f"Disease classes: {len(class_names)} | train={len(train_dl.dataset)} val={len(val_dl.dataset)}")

    model = build_model(arch, num_classes=len(class_names), pretrained=True)
    weights = class_weights_for_dataset(train_dl.dataset)
    return train_model(
        model, train_dl, val_dl,
        epochs=epochs, lr=lr, device=device,
        class_names=class_names, arch=arch, ckpt_path=config.disease_ckpt(arch),
        class_weights=weights, resume=resume, ckpt_every=ckpt_every,
    )


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Train one disease backbone (supports --resume)")
    ap.add_argument("--arch", required=True, choices=config.DISEASE_ARCHS)
    ap.add_argument("--source", default=config.DEFAULT_DISEASE_SOURCE, choices=("plantvillage", "bd", "combined"))
    ap.add_argument("--epochs", type=int, default=config.DISEASE_EPOCHS)
    ap.add_argument("--batch", type=int, default=config.DISEASE_BATCH)
    ap.add_argument("--lr", type=float, default=config.DISEASE_LR)
    ap.add_argument("--resume", action="store_true", help="Continue from models/disease_{arch}.train.pt")
    ap.add_argument("--ckpt-every", type=int, default=1, help="Extra epoch-tagged snapshots every N epochs")
    args = ap.parse_args(argv)
    train_one(
        args.arch, args.epochs, args.batch, args.lr, source=args.source,
        resume=args.resume, ckpt_every=args.ckpt_every,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
