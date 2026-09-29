"""Three-level inference: leaf gate -> crop type -> 3-model disease.

Level 3 runs EfficientNet-B3, ResNet-50, and DenseNet-121 (aligned by class
name when checkpoint vocabularies differ), masks to the Level-2 crop, then
picks the single model prediction with the highest confidence.

If `models/leaf_type.pt` is missing, Level 2 aggregates Level-3 disease
probabilities by plant/crop so the top-3 picker still works.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
from PIL import Image

from . import config
from .data import infer_transform
from .image_io import load_rgb_image
from .knowledge import advice_for
from .label_map import classes_for_crop, crop_from_class, is_other_crop
from .models import load_checkpoint


def _ensure_other_option(top3: List[dict]) -> List[dict]:
    """Always offer Other so an out-of-set plant is not forced into a trained crop."""
    out = [dict(x) for x in (top3 or [])]
    if not any(is_other_crop(x.get("crop")) for x in out):
        out.append({"crop": config.CROP_OTHER_LABEL, "confidence": 0.0})
    return out


def _decorate_crop(stage: dict) -> dict:
    """Flag low-confidence L2 as Other and append the Other picker option."""
    stage = dict(stage or {})
    top3 = stage.get("top3") or []
    if not top3 and stage.get("crop"):
        top3 = [{"crop": stage.get("crop"), "confidence": stage.get("confidence") or 0.0}]
    stage["top3"] = _ensure_other_option(top3)
    conf = float(stage.get("confidence") or 0.0)
    if (
        stage.get("available")
        and not is_other_crop(stage.get("crop"))
        and conf < config.CROP_OTHER_THRESHOLD
    ):
        stage["guess"] = stage.get("crop")
        stage["crop"] = config.CROP_OTHER_LABEL
        stage["is_other"] = True
    else:
        stage["is_other"] = is_other_crop(stage.get("crop"))
    return stage


def _other_crop_message(lang: str) -> str:
    if (lang or "").startswith("en"):
        return (
            "This plant is not in AgroScan's trained crops, so disease "
            "diagnosis was skipped. Pick a listed crop if this is a known plant, "
            "or use Other if it is not."
        )
    return (
        "এই গাছ AgroScan-এর প্রশিক্ষিত ফসলের তালিকায় নেই, তাই রোগ "
        "বিশ্লেষণ করা হয়নি। তালিকার কোনো ফসল হলে সেটি বেছে নিন, "
        "না হলে অন্যান্য চাপুন।"
    )


def _pretty(class_name: str) -> Dict[str, str]:
    """Parse canonical labels like 'Tomato___Late_blight' or 'Rice___Blast'."""
    if "___" in class_name:
        plant, cond = class_name.split("___", 1)
    elif "_" in class_name:
        plant, cond = class_name.split("_", 1)
    else:
        plant, cond = class_name, ""
    plant = plant.replace("_", " ").replace("(", "(").strip()
    cond_clean = cond.replace("_", " ").strip()
    if cond_clean.lower().startswith("variety "):
        return {
            "plant": plant,
            "condition": cond_clean,
            "is_healthy": False,
        }
    is_healthy = cond_clean.lower() in ("healthy", "normal")
    return {
        "plant": plant,
        "condition": "Healthy" if is_healthy else cond_clean,
        "is_healthy": is_healthy,
    }


class LoadedModel:
    def __init__(self, path: Path, device: str):
        self.model, self.class_names, self.meta = load_checkpoint(path, device)
        self.arch = self.meta["arch"]
        self.size = config.INPUT_SIZE.get(self.arch, config.DEFAULT_INPUT_SIZE)
        self.tf = infer_transform(self.size)
        self.device = device

    @torch.no_grad()
    def probs(self, img: Image.Image) -> torch.Tensor:
        x = self.tf(img).unsqueeze(0).to(self.device)
        return F.softmax(self.model(x), dim=1).squeeze(0).cpu()


class InferenceEngine:
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Stage 1 - leaf gate (optional but recommended)
        self.leaf: Optional[LoadedModel] = None
        if config.LEAF_CKPT.exists():
            self.leaf = LoadedModel(config.LEAF_CKPT, self.device)

        # Level 2 - crop / leaf type
        self.crop: Optional[LoadedModel] = None
        if config.CROP_CKPT.exists():
            self.crop = LoadedModel(config.CROP_CKPT, self.device)

        # Level 3 - disease ensemble (prefer largest class vocabulary as base)
        self.disease: List[LoadedModel] = []
        for arch in config.DISEASE_ARCHS:
            p = config.disease_ckpt(arch)
            if p.exists():
                self.disease.append(LoadedModel(p, self.device))
        if self.disease:
            self.disease.sort(key=lambda m: len(m.class_names), reverse=True)
            self.disease_classes = list(self.disease[0].class_names)
            self._class_index = {n: i for i, n in enumerate(self.disease_classes)}
        else:
            self.disease_classes = []
            self._class_index = {}

    # ------------------------------------------------------------------ #
    @property
    def ready(self) -> bool:
        return len(self.disease) > 0

    def status(self) -> dict:
        return {
            "device": self.device,
            "leaf_gate_loaded": self.leaf is not None,
            "crop_model_loaded": self.crop is not None,
            "crop_fallback": self.crop is None and bool(self.disease),
            "disease_models_loaded": [config.model_display_name(m.arch) for m in self.disease],
            "num_disease_classes": len(self.disease_classes),
            "levels": {
                "l1_leaf": self.leaf is not None,
                "l2_plant_type": self.crop is not None or bool(self.disease),
                "l3_disease": bool(self.disease),
            },
        }

    # ------------------------------------------------------------------ #
    def _align_probs(self, probs: torch.Tensor, class_names: List[str]) -> torch.Tensor:
        """Map a model's softmax onto the shared disease class vector."""
        out = torch.zeros(len(self.disease_classes), dtype=probs.dtype)
        for i, name in enumerate(class_names):
            j = self._class_index.get(name)
            if j is not None:
                out[j] = probs[i]
        s = out.sum().clamp_min(1e-8)
        return out / s

    def _disease_prob_stack(
        self, img: Image.Image
    ) -> Tuple[torch.Tensor, List[torch.Tensor], List[LoadedModel]]:
        """Per-model aligned probs + mean (unmasked)."""
        aligned: List[torch.Tensor] = []
        for m in self.disease:
            p = m.probs(img)
            if len(m.class_names) == len(self.disease_classes) and list(m.class_names) == self.disease_classes:
                aligned.append(p)
            else:
                aligned.append(self._align_probs(p, m.class_names))
        # Average only over models that put mass on each class (avoids diluting
        # EfficientNet-only BD/extra classes with zeros from older 38-class ckpts).
        stack = torch.stack(aligned)
        mass = (stack > 0).float()
        denom = mass.sum(0).clamp_min(1.0)
        mean_p = (stack * mass).sum(0) / denom
        mean_p = mean_p / mean_p.sum().clamp_min(1e-8)
        return mean_p, aligned, self.disease

    def _leaf_stage(self, img: Image.Image) -> dict:
        if self.leaf is None:
            return {
                "available": False,
                "is_leaf": True,  # no gate trained -> don't block
                "note": "Leaf gate model not trained; skipping leaf check.",
            }
        p = self.leaf.probs(img)
        names = [str(n).strip().lower() for n in self.leaf.class_names]
        if "leaf" in names:
            leaf_idx = names.index("leaf")
        elif "non_leaf" in names or "non-leaf" in names:
            non_key = "non_leaf" if "non_leaf" in names else "non-leaf"
            leaf_idx = 1 - names.index(non_key) if len(names) == 2 else 0
        else:
            leaf_idx = int(torch.argmax(p).item())
        leaf_prob = float(p[leaf_idx])
        is_leaf = leaf_prob >= config.LEAF_ACCEPT_THRESHOLD
        return {
            "available": True,
            "model": config.model_display_name(self.leaf.arch),
            "is_leaf": is_leaf,
            "leaf_probability": round(leaf_prob, 4),
            "label": "leaf" if is_leaf else "non_leaf",
        }

    def _top_crops_from_probs(self, class_probs: torch.Tensor) -> List[dict]:
        scores: Dict[str, float] = {}
        for i, cls in enumerate(self.disease_classes):
            crop = crop_from_class(cls)
            scores[crop] = scores.get(crop, 0.0) + float(class_probs[i])
        total = sum(scores.values()) or 1.0
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [
            {"crop": name, "confidence": round(score / total, 4)}
            for name, score in ranked[:3]
        ]

    def _crop_stage(
        self,
        img: Image.Image,
        *,
        disease_mean: Optional[torch.Tensor] = None,
    ) -> dict:
        if self.crop is not None:
            p = self.crop.probs(img)
            conf, idx = torch.max(p, dim=0)
            crop = self.crop.class_names[int(idx)]
            top = torch.topk(p, k=min(3, p.numel()))
            return _decorate_crop(
                {
                    "available": True,
                    "source": "leaf_type",
                    "model": config.model_display_name(self.crop.arch),
                    "crop": crop,
                    "confidence": round(float(conf), 4),
                    "top3": [
                        {
                            "crop": self.crop.class_names[int(i)],
                            "confidence": round(float(v), 4),
                        }
                        for v, i in zip(top.values, top.indices)
                    ],
                }
            )

        if not self.disease:
            return {
                "available": False,
                "crop": None,
                "note": "Leaf-type model not trained; disease stage will not mask by crop.",
            }

        mean_p = disease_mean
        if mean_p is None:
            mean_p, _, _ = self._disease_prob_stack(img)
        top3 = self._top_crops_from_probs(mean_p)
        best = top3[0] if top3 else {"crop": None, "confidence": 0.0}
        return _decorate_crop(
            {
                "available": True,
                "source": "disease_aggregate",
                "model": "Disease ensemble (plant from class probs)",
                "crop": best.get("crop"),
                "confidence": best.get("confidence", 0.0),
                "top3": top3,
                "note": (
                    "Dedicated leaf_type.pt not found; plant type estimated "
                    "from disease models."
                ),
            }
        )

    def _mask_probs(self, probs: torch.Tensor, crop: Optional[str]) -> torch.Tensor:
        if not crop or not self.disease_classes or is_other_crop(crop):
            if is_other_crop(crop):
                return torch.zeros_like(probs)
            return probs
        idx = classes_for_crop(self.disease_classes, crop)
        masked = torch.zeros_like(probs)
        take = probs[idx]
        take = take / take.sum().clamp_min(1e-8)
        masked[idx] = take
        return masked

    def _disease_stage(
        self,
        img: Image.Image,
        crop: Optional[str] = None,
        *,
        land_size: float | None = None,
        land_unit: str = "decimal",
        lang: str = "bn",
        aligned_probs: Optional[List[torch.Tensor]] = None,
        models: Optional[List[LoadedModel]] = None,
    ) -> dict:
        models = models or self.disease
        if aligned_probs is None:
            _, aligned_probs, models = self._disease_prob_stack(img)

        per_model = []
        for m, raw_p in zip(models, aligned_probs):
            p = self._mask_probs(raw_p, crop)
            conf, idx = torch.max(p, dim=0)
            top_k = min(3, int((p > 0).sum().item()) or 1)
            top = torch.topk(p, k=top_k)
            cls = self.disease_classes[int(idx)]
            info = _pretty(cls)
            per_model.append(
                {
                    "model": config.model_display_name(m.arch),
                    "prediction": cls,
                    "plant": info["plant"],
                    "condition": info["condition"],
                    "is_healthy": info["is_healthy"],
                    "confidence": round(float(conf), 4),
                    "top3": [
                        {
                            "label": self.disease_classes[int(i)],
                            **_pretty(self.disease_classes[int(i)]),
                            "confidence": round(float(v), 4),
                        }
                        for v, i in zip(top.values, top.indices)
                    ],
                }
            )

        if not per_model:
            return {
                "models": [],
                "best_answer": None,
                "selection": "highest_confidence",
            }

        # NEVER average — pick the single model with the highest confidence.
        winner = max(per_model, key=lambda pm: float(pm.get("confidence") or 0.0))
        best_cls = winner["prediction"]
        conf = float(winner["confidence"])
        info = _pretty(best_cls)
        for pm in per_model:
            pm["is_highest"] = (
                pm["model"] == winner["model"]
                and float(pm.get("confidence") or 0.0) == conf
            )
        agree = sum(1 for pm in per_model if pm["prediction"] == best_cls)
        if len(per_model) == 1:
            method = per_model[0]["model"]
            agreement = ""
        elif lang == "en":
            method = f"Highest confidence — {winner['model']} ({round(conf * 100, 1)}%)"
            agreement = f"{agree}/{len(per_model)} models agree"
        else:
            method = f"সর্বোচ্চ আত্মবিশ্বাস — {winner['model']} ({round(conf * 100, 1)}%)"
            agreement = f"{agree}/{len(per_model)}টি মডেল একমত"
        best = {
            "prediction": best_cls,
            "plant": info["plant"],
            "condition": info["condition"],
            "is_healthy": info["is_healthy"],
            "confidence": round(conf, 4),
            "winning_model": winner["model"],
            "selection": "highest_confidence",
            "method": method,
            "agreement": agreement,
            "uncertain": conf < config.UNCERTAIN_THRESHOLD,
            "low_confidence": conf < config.LOW_CONFIDENCE_THRESHOLD,
            "recommendation": (
                "আত্মবিশ্বাস ৮০% এর নিচে। পরিষ্কার, কাছ থেকে একটি পাতার ছবি তুলুন "
                "(সাদা ব্যাকগ্রাউন্ড, ভালো আলো), অথবা কৃষি কর্মকর্তা/পশুচিকিৎসকের সাথে "
                "যোগাযোগ করুন (কৃষি: ১৬১২৩, পশুচিকিৎসা: ১৬৩৫৮)।"
                if conf < config.LOW_CONFIDENCE_THRESHOLD
                else None
            ),
            "advice": advice_for(
                best_cls, lang, land_size=land_size, land_unit=land_unit or "decimal"
            ),
            "top3": list(winner.get("top3") or []),
        }
        return {
            "models": per_model,
            "best_answer": best,
            "selection": "highest_confidence",
        }

    # ------------------------------------------------------------------ #
    def predict(
        self,
        img: Image.Image,
        crop_override: Optional[str] = None,
        *,
        land_size: float | None = None,
        land_unit: str = "decimal",
        lang: str = "bn",
    ) -> dict:
        img = load_rgb_image(img, fallback_size=None)
        leaf = self._leaf_stage(img)
        result = {
            "stage1_leaf_gate": leaf,
            "stage2_leaf_type": None,
            "stage3_disease": None,
            "stage2_disease": None,  # alias for older web/mobile clients
        }
        if not leaf["is_leaf"]:
            result["message"] = (
                "এই ছবিটি পাতা বলে মনে হয় না, তাই রোগ বিশ্লেষণ করা হয়নি।"
            )
            return result

        # If leaf_type.pt is missing, L2 reuses one disease forward pass.
        disease_mean = None
        aligned = None
        models = None
        if self.disease and self.crop is None:
            disease_mean, aligned, models = self._disease_prob_stack(img)

        crop = self._crop_stage(img, disease_mean=disease_mean)
        if crop_override:
            crop = dict(crop)
            crop["crop"] = crop_override
            crop["is_other"] = is_other_crop(crop_override)
            crop["user_selected"] = True
            crop["needs_user_pick"] = False
            crop["top3"] = _ensure_other_option(crop.get("top3") or [])
        elif crop.get("available") and (
            crop.get("confidence", 1.0) < config.CROP_USER_CONFIRM_THRESHOLD
            or crop.get("is_other")
        ):
            crop = dict(crop)
            crop["needs_user_pick"] = True
        else:
            crop = dict(crop) if crop else crop
            if crop:
                crop["needs_user_pick"] = False
        result["stage2_leaf_type"] = crop
        if not self.disease:
            result["message"] = "No disease models trained yet."
            return result
        chosen_crop = crop_override or (crop.get("crop") if crop else None)
        if crop and crop.get("needs_user_pick") and not crop_override:
            result["message"] = (
                "ফসল চেনার আত্মবিশ্বাস ৯০% এর নিচে। নিচ থেকে সঠিক ফসল বেছে নিন, "
                "অথবা তালিকায় না থাকলে অন্যান্য চাপুন।"
                if not (lang or "").startswith("en")
                else (
                    "Crop confidence is below 90%. Pick the correct crop below, "
                    "or Other if this plant is not in the list."
                )
            )
            return result
        if is_other_crop(chosen_crop):
            result["message"] = _other_crop_message(lang)
            return result
        if aligned is None:
            disease_mean, aligned, models = self._disease_prob_stack(img)
        disease = self._disease_stage(
            img,
            chosen_crop,
            land_size=land_size,
            land_unit=land_unit or "decimal",
            lang=lang or "bn",
            aligned_probs=aligned,
            models=models,
        )
        result["stage3_disease"] = disease
        result["stage2_disease"] = disease
        return result
