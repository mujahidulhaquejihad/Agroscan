"""Train Level-2 leaf-type (crop) classifier."""
from __future__ import annotations

import argparse
import sys

import torch

from . import config
from .data import class_weights_for_dataset, crop_loaders
from .engine import train_model
from .models import build_model


def train_crop(
    *,
    epochs: int | None = None,
    batch: int | None = None,
    lr: float | None = None,
    arch: str | None = None,
    resume: bool = False,
    ckpt_every: int = 1,
) -> float:
    epochs = config.CROP_EPOCHS if epochs is None else epochs
    batch = config.CROP_BATCH if batch is None else batch
    lr = config.CROP_LR if lr is None else lr
    arch = config.CROP_ARCH if arch is None else arch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(config.SEED)
    size = config.INPUT_SIZE.get(arch, config.DEFAULT_INPUT_SIZE)

    print(f"Device={device} | arch={arch} | input={size} | resume={resume}")
    train_dl, val_dl, class_names = crop_loaders(size, batch)
    print(f"Crops: {class_names}")

    model = build_model(arch, num_classes=len(class_names), pretrained=True)
    weights = class_weights_for_dataset(train_dl.dataset)
    return train_model(
        model, train_dl, val_dl,
        epochs=epochs, lr=lr, device=device,
        class_names=class_names, arch=arch, ckpt_path=config.CROP_CKPT,
        class_weights=weights, resume=resume, ckpt_every=ckpt_every,
    )


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Train crop/leaf-type (supports --resume)")
    ap.add_argument("--epochs", type=int, default=config.CROP_EPOCHS)
    ap.add_argument("--batch", type=int, default=config.CROP_BATCH)
    ap.add_argument("--lr", type=float, default=config.CROP_LR)
    ap.add_argument("--arch", default=config.CROP_ARCH)
    ap.add_argument("--resume", action="store_true", help="Continue from models/leaf_type.train.pt")
    ap.add_argument("--ckpt-every", type=int, default=1, help="Extra epoch-tagged snapshots every N epochs")
    args = ap.parse_args(argv)
    train_crop(
        epochs=args.epochs, batch=args.batch, lr=args.lr, arch=args.arch,
        resume=args.resume, ckpt_every=args.ckpt_every,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
