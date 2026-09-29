"""Export L1/L2/L3 ONNX + a slim advice pack for the Android APK.

Offline scan uses leaf_gate + leaf_type + EfficientNet-B3 only (skip ResNet/DenseNet
to keep the APK installable). Chat still hits the hosted API when online.

  python scripts/export_mobile_onnx.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agroscan import config
from agroscan.label_map import crop_from_class
from agroscan.models import load_checkpoint
from agroscan.knowledge import advice_for

OUT_DIR = ROOT / "models" / "mobile"
PACK_PATH = ROOT / "web" / "offline-pack.json"

EXPORTS = (
    ("leaf_gate", config.LEAF_CKPT, "leaf_gate.onnx"),
    ("leaf_type", config.CROP_CKPT, "leaf_type.onnx"),
    ("disease", config.disease_ckpt("efficientnet_b3"), "disease_efficientnet_b3.onnx"),
)


def _slim_advice(info: dict | None) -> dict | None:
    if not info:
        return None
    steps = []
    for s in info.get("next_steps") or []:
        if isinstance(s, dict):
            steps.append({"title": s.get("title") or "", "detail": s.get("detail") or ""})
        elif s:
            steps.append({"title": str(s), "detail": ""})
    return {
        "title": info.get("title") or "",
        "description": info.get("description") or info.get("summary") or "",
        "treatment": list(info.get("treatment") or []),
        "prevention": list(info.get("prevention") or []),
        "next_steps": steps,
        "when_to_call_helpline": info.get("when_to_call_helpline") or "",
        "matched_key": info.get("matched_key"),
        "class_name": info.get("class_name"),
    }


def _export_one(ckpt: Path, onnx_path: Path) -> tuple[str, list[str], int]:
    model, class_names, meta = load_checkpoint(ckpt, device="cpu")
    arch = meta["arch"]
    size = int(config.INPUT_SIZE.get(arch, config.DEFAULT_INPUT_SIZE))
    dummy = torch.zeros(1, 3, size, size)
    model.eval()
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            input_names=["input"],
            output_names=["logits"],
            opset_version=17,
            dynamo=False,
        )
    # ponytail: numerical check vs PyTorch on the dummy zeros tensor
    with torch.no_grad():
        pt = model(dummy).softmax(dim=1).squeeze(0)
    try:
        import onnxruntime as ort

        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        raw = sess.run(["logits"], {"input": dummy.numpy()})[0]
        import numpy as np

        ex = np.exp(raw - raw.max(axis=1, keepdims=True))
        onnx_p = ex / ex.sum(axis=1, keepdims=True)
        max_delta = float(np.max(np.abs(pt.numpy() - onnx_p[0])))
        assert max_delta < 1e-4, f"{onnx_path.name} ORT delta {max_delta}"
        print(f"  check {onnx_path.name}: max softmax delta {max_delta:.2e}")
    except ImportError:
        print(f"  skip ORT check (pip install onnxruntime); pt sum={float(pt.sum()):.4f}")
    return arch, list(class_names), size


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pack = {
        "chat_api": "https://agroscan.mujahidulhaquejihad.com",
        "mean": config.MEAN,
        "std": config.STD,
        "leaf_accept": config.LEAF_ACCEPT_THRESHOLD,
        "crop_other": config.CROP_OTHER_THRESHOLD,
        "crop_confirm": config.CROP_USER_CONFIRM_THRESHOLD,
        "uncertain": config.UNCERTAIN_THRESHOLD,
        "low_confidence": config.LOW_CONFIDENCE_THRESHOLD,
        "other_label": config.CROP_OTHER_LABEL,
        "models": {},
        "advice": {},
    }
    for key, ckpt, filename in EXPORTS:
        if not ckpt.exists():
            raise SystemExit(f"Missing {ckpt}")
        print(f"export {key} <- {ckpt.name}")
        arch, names, size = _export_one(ckpt, OUT_DIR / filename)
        pack["models"][key] = {
            "file": filename,
            "arch": arch,
            "size": size,
            "classes": names,
        }
        print(f"  {arch} {size}px {len(names)} classes -> {filename}")

    disease_names = pack["models"]["disease"]["classes"]
    for name in disease_names:
        pack["advice"][name] = {
            "crop": crop_from_class(name),
            "bn": _slim_advice(advice_for(name, "bn")),
            "en": _slim_advice(advice_for(name, "en")),
        }
    PACK_PATH.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {PACK_PATH} ({PACK_PATH.stat().st_size / 1024:.0f} KB)")
    for p in OUT_DIR.glob("*.onnx"):
        print(f"  {p.name} {p.stat().st_size / 1024 / 1024:.1f} MB")
    assert len(disease_names) >= 100, len(disease_names)
    print("ok")


if __name__ == "__main__":
    main()
