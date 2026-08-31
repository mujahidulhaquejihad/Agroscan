"""Model factory + checkpoint save/load helpers."""
from __future__ import annotations

from typing import List

import torch
import torch.nn as nn
import torchvision.models as tvm


def build_model(arch: str, num_classes: int, pretrained: bool = True) -> nn.Module:
    """Create a backbone with an ImageNet head swapped for `num_classes`."""
    weights = "DEFAULT" if pretrained else None

    if arch == "efficientnet_b3":
        m = tvm.efficientnet_b3(weights=weights)
        in_f = m.classifier[1].in_features
        m.classifier[1] = nn.Linear(in_f, num_classes)

    elif arch == "efficientnet_b0":
        m = tvm.efficientnet_b0(weights=weights)
        in_f = m.classifier[1].in_features
        m.classifier[1] = nn.Linear(in_f, num_classes)

    elif arch == "resnet50":
        m = tvm.resnet50(weights=weights)
        m.fc = nn.Linear(m.fc.in_features, num_classes)

    elif arch == "densenet121":
        m = tvm.densenet121(weights=weights)
        m.classifier = nn.Linear(m.classifier.in_features, num_classes)

    elif arch == "mobilenet_v3_large":
        m = tvm.mobilenet_v3_large(weights=weights)
        in_f = m.classifier[3].in_features
        m.classifier[3] = nn.Linear(in_f, num_classes)

    else:
        raise ValueError(f"Unknown architecture: {arch}")

    return m


def save_checkpoint(path, model: nn.Module, arch: str, class_names: List[str], meta: dict | None = None):
    torch.save(
        {
            "arch": arch,
            "class_names": class_names,
            "state_dict": model.state_dict(),
            "meta": meta or {},
        },
        path,
    )


def save_training_state(path, payload: dict) -> None:
    """Full training snapshot for resume (model + optimizer + scheduler + scaler)."""
    torch.save(payload, path)


def load_training_state(path, map_location: str = "cpu"):
    """Return training snapshot dict, or None if missing."""
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    return torch.load(p, map_location=map_location, weights_only=False)


def load_checkpoint(path, device: str = "cpu"):
    """Return (model.eval(), class_names, meta)."""
    ckpt = torch.load(path, map_location=device, weights_only=False)
    arch = ckpt["arch"]
    class_names = ckpt["class_names"]
    model = build_model(arch, num_classes=len(class_names), pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    meta = dict(ckpt.get("meta", {}))
    meta["arch"] = arch
    return model, class_names, meta
