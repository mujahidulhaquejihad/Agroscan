"""Reusable training / evaluation loop (mixed precision, cosine LR, resume)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from tqdm import tqdm

from . import config
from .models import save_checkpoint, save_training_state, load_training_state


class FocalLoss(nn.Module):
    """Focal CE (D). Optional class weights further boost rare labels."""

    def __init__(self, gamma: float = 2.0, weight: Optional[torch.Tensor] = None):
        super().__init__()
        self.gamma = gamma
        if weight is None:
            self.weight = None
        else:
            self.register_buffer("weight", weight.float())

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        w = self.weight.to(logits.device) if self.weight is not None else None
        ce = F.cross_entropy(logits, target, weight=w, reduction="none")
        pt = torch.exp(-ce)
        return (((1.0 - pt) ** self.gamma) * ce).mean()


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> float:
    model.eval()
    correct = total = 0
    for x, y in tqdm(loader, desc="eval", leave=False):
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        preds = model(x).argmax(1)
        correct += (preds == y).sum().item()
        total += y.numel()
    return correct / max(total, 1)


def train_resume_path(ckpt_path) -> Path:
    p = Path(ckpt_path)
    return p.with_name(p.stem + ".train.pt")


def train_model(
    model: nn.Module,
    train_dl: DataLoader,
    val_dl: DataLoader,
    *,
    epochs: int,
    lr: float,
    device: str,
    class_names: List[str],
    arch: str,
    ckpt_path,
    class_weights: Optional[torch.Tensor] = None,
    resume: bool = False,
    ckpt_every: int = 1,
) -> float:
    """Train and save best weights to `ckpt_path`.

    Also writes a full resume snapshot to `{stem}.train.pt` each epoch (and
    every `ckpt_every` epochs for an extra epoch-tagged copy when > 1).
    Use ``resume=True`` to continue from the latest `.train.pt`.
    """
    model.to(device)
    weights = class_weights.to(device) if class_weights is not None else None
    if config.USE_FOCAL_LOSS:
        criterion: nn.Module = FocalLoss(gamma=config.FOCAL_GAMMA, weight=weights)
        criterion.to(device)
    else:
        criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    use_amp = device.startswith("cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_acc = 0.0
    start_epoch = 1
    resume_path = train_resume_path(ckpt_path)

    if resume:
        state = load_training_state(resume_path, map_location=device)
        if state is None and Path(ckpt_path).exists():
            # Fall back to best weights only (optimizer/scheduler reset).
            from .models import load_checkpoint
            print(f"[resume] no {resume_path.name}; loading weights from {ckpt_path}")
            m2, names2, meta = load_checkpoint(ckpt_path, device=device)
            if names2 != class_names:
                raise RuntimeError(
                    f"Class list mismatch on resume: ckpt has {len(names2)} classes, "
                    f"data has {len(class_names)}"
                )
            model.load_state_dict(m2.state_dict())
            best_acc = float((meta or {}).get("val_acc") or 0.0)
            start_epoch = int((meta or {}).get("epoch") or 0) + 1
        elif state is None:
            print(f"[resume] no checkpoint at {resume_path}; starting from scratch")
        else:
            if state.get("class_names") != class_names:
                raise RuntimeError(
                    f"Class list mismatch on resume: ckpt has {len(state.get('class_names') or [])} "
                    f"classes, data has {len(class_names)}"
                )
            if state.get("arch") and state["arch"] != arch:
                raise RuntimeError(f"Arch mismatch: ckpt={state.get('arch')} vs {arch}")
            model.load_state_dict(state["model"])
            if state.get("optimizer"):
                optimizer.load_state_dict(state["optimizer"])
            if state.get("scheduler"):
                scheduler.load_state_dict(state["scheduler"])
            if state.get("scaler") is not None and use_amp:
                try:
                    scaler.load_state_dict(state["scaler"])
                except Exception as e:
                    print(f"[resume] scaler state skipped: {e}")
            best_acc = float(state.get("best_acc") or 0.0)
            start_epoch = int(state.get("epoch") or 0) + 1
            print(
                f"[resume] loaded {resume_path.name} @ epoch {start_epoch - 1} "
                f"(best_acc={best_acc:.4f})"
            )

    if start_epoch > epochs:
        print(f"[{arch}] already finished {epochs} epochs (resume start={start_epoch})")
        return best_acc

    for epoch in range(start_epoch, epochs + 1):
        model.train()
        running, seen, t0 = 0.0, 0, time.time()
        pbar = tqdm(train_dl, desc=f"{arch} epoch {epoch}/{epochs}")
        for x, y in pbar:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=use_amp):
                out = model(x)
                loss = criterion(out, y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += loss.item() * x.size(0)
            seen += x.size(0)
            pbar.set_postfix(loss=f"{running / seen:.3f}")
        scheduler.step()

        acc = evaluate(model, val_dl, device)
        dt = time.time() - t0
        print(f"[{arch}] epoch {epoch}: val_acc={acc:.4f}  ({dt:.0f}s)")

        payload = {
            "arch": arch,
            "class_names": class_names,
            "epoch": epoch,
            "epochs": epochs,
            "best_acc": best_acc,
            "lr": lr,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "scaler": scaler.state_dict() if use_amp else None,
            "meta": {"val_acc": acc, "epoch": epoch},
        }
        save_training_state(resume_path, payload)
        if ckpt_every > 1 and epoch % ckpt_every == 0:
            tagged = resume_path.with_name(f"{resume_path.stem}.e{epoch}.pt")
            save_training_state(tagged, payload)
            print(f"   -> epoch snapshot {tagged.name}")

        if acc >= best_acc:
            best_acc = acc
            payload["best_acc"] = best_acc
            save_checkpoint(
                ckpt_path, model, arch, class_names,
                meta={"val_acc": acc, "epoch": epoch},
            )
            save_training_state(resume_path, payload)
            print(f"   -> saved best checkpoint ({acc:.4f}) to {ckpt_path}")

    print(f"[{arch}] best val_acc = {best_acc:.4f}")
    return best_acc
