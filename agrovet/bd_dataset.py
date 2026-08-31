"""Bangladesh crop disease dataset (Hugging Face).

Repo: Saon110/bd-crop-vegetable-plant-disease-dataset
(~123k images, 94 classes, train/valid/test splits)

The dataset is gated — accept terms on Hugging Face, then:
    huggingface-cli login
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import config
from .image_io import load_rgb_image

# User snippet uses a shortened id; the Hub repo id is the full name below.
BD_HF_ALIASES = (
    "Saon110/bd-crop-vegetable-plant-disease-dataset",
    "Saon110/bd-crop-veg-plant-disease-dataset",
)


def _require_datasets():
    try:
        from datasets import load_dataset, load_dataset_builder
    except ImportError as e:
        raise ImportError(
            "Install Hugging Face datasets: python -m pip install datasets huggingface_hub"
        ) from e
    return load_dataset, load_dataset_builder


def hf_repo_id() -> str:
    return config.BD_HF_DATASET


def hf_access_help() -> str:
    return (
        "The Bangladesh dataset is gated on Hugging Face.\n"
        "1) Open https://huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset\n"
        "2) Log in and click 'Agree' to the dataset terms\n"
        "3) Run: huggingface-cli login\n"
        "4) Retry training or: python -m agrovet.prepare_bd_dataset info"
    )


def load_bd_splits(cache_dir: Optional[str] = None):
    """Load train / valid / test from the Hub (cached under ~/.cache/huggingface)."""
    load_dataset, _ = _require_datasets()
    kwargs = {}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    last_err = None
    for repo_id in BD_HF_ALIASES:
        try:
            return load_dataset(repo_id, **kwargs)
        except Exception as e:
            last_err = e
            err = str(e).lower()
            if "gated" in err or "authenticated" in err or "401" in err:
                raise PermissionError(hf_access_help()) from e
            if "doesn't exist" in err or "not found" in err:
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("Could not load Bangladesh dataset from Hugging Face.")


def _label_names_from_train(train_ds) -> List[str]:
    label_feat = train_ds.features.get("label")
    if label_feat is not None and hasattr(label_feat, "names") and label_feat.names:
        return list(label_feat.names)
    if "label_name" in train_ds.column_names:
        return sorted(set(train_ds.unique("label_name")))
    raise ValueError("No class names in dataset (expected ClassLabel or label_name).")


def _row_label_name(row, names: List[str]) -> str:
    if "label_name" in row and row["label_name"]:
        return str(row["label_name"])
    return names[int(row["label"])]


def bd_label_names(cache_dir: Optional[str] = None) -> List[str]:
    """Class names from the train split."""
    ds = load_bd_splits(cache_dir)
    return _label_names_from_train(ds["train"])


def bd_split_stats() -> Dict[str, int]:
    ds = load_bd_splits()
    return {split: len(ds[split]) for split in ds.keys()}


def export_to_imagefolder(
    out_dir: Optional[Path] = None,
    *,
    splits: Tuple[str, ...] = ("train", "valid", "test"),
    max_per_class: Optional[int] = None,
) -> Path:
    """Export Hub splits to ImageFolder layout under Datasets/."""
    from tqdm import tqdm

    out = Path(out_dir or config.BD_EXPORT_DIR)
    ds = load_bd_splits()
    names = _label_names_from_train(ds["train"])

    for split in splits:
        if split not in ds:
            continue
        split_ds = ds[split]
        counts: Dict[int, int] = {}
        print(f"\nExporting {split}: {len(split_ds)} images -> {out / split}")
        for i, row in enumerate(tqdm(split_ds, desc=split, unit="img")):
            label_id = int(row["label"])
            if max_per_class is not None and counts.get(label_id, 0) >= max_per_class:
                continue
            class_name = _safe_class_dir(_row_label_name(row, names))
            dest_dir = out / split / class_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            img = load_rgb_image(row["image"], fallback_size=None)
            img.save(dest_dir / f"{split}_{i:06d}.jpg", quality=92)
            counts[label_id] = counts.get(label_id, 0) + 1
    print(f"\nDone. Exported to {out.resolve()}")
    return out


def _safe_class_dir(name: str) -> str:
    """Folder-safe class name (Windows-compatible)."""
    return name.replace("/", "_").replace("\\", "_").strip() or "unknown"


def print_dataset_info():
    load_dataset, _ = _require_datasets()
    print(f"Hub repo: {hf_repo_id()}")
    ds = load_bd_splits()
    names = _label_names_from_train(ds["train"])
    print(f"Total classes: {len(names)}")
    for split in ("train", "valid", "test"):
        if split in ds:
            print(f"{split} samples: {len(ds[split])}")
    print("\nFirst 15 classes:")
    for n in names[:15]:
        print(f"  - {n}")
    if len(names) > 15:
        print(f"  ... and {len(names) - 15} more")
