"""Datasets, transforms and dataloaders for both stages."""
from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import ConcatDataset, DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms
from torchvision.datasets import ImageFolder

from . import config
from .bd_leaf_dataset import ensure_bd_leaf_extracted
from .image_io import gather_images, is_image_path, load_rgb_image
from .label_map import (
    LabelRegistry,
    is_variety_class,
    merge_class_name,
    summarize_registry,
)


def _folder_image_loader(path: str):
    """ImageFolder loader that survives Windows paths longer than MAX_PATH."""
    return load_rgb_image(path, fallback_size=None)


# --------------------------------------------------------------------------- #
# Transforms
# --------------------------------------------------------------------------- #
def build_transforms(input_size: int, train: bool) -> transforms.Compose:   ###
    if train:
        return transforms.Compose(
            [
                transforms.RandomResizedCrop(input_size, scale=(0.7, 1.0)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(20),
                transforms.ColorJitter(0.2, 0.2, 0.2),
                transforms.ToTensor(),
                transforms.Normalize(config.MEAN, config.STD),
            ]
        )
    resize = int(input_size * 1.15)
    return transforms.Compose(
        [
            transforms.Resize(resize),
            transforms.CenterCrop(input_size),
            transforms.ToTensor(),
            transforms.Normalize(config.MEAN, config.STD),
        ]
    )


def infer_transform(input_size: int) -> transforms.Compose:
    return build_transforms(input_size, train=False)


def _dataloader_kwargs(*, shuffle: bool, batch: int, drop_last: bool = False) -> dict:
    kw: dict = {
        "batch_size": batch,
        "shuffle": shuffle,
        "num_workers": config.NUM_WORKERS,
        "pin_memory": True,
        "drop_last": drop_last,
    }
    if config.NUM_WORKERS > 0:
        kw["persistent_workers"] = True
        kw["prefetch_factor"] = config.PREFETCH_FACTOR
    return kw


# --------------------------------------------------------------------------- #
# Shared dataset helpers
# --------------------------------------------------------------------------- #
class ImageListDataset(Dataset):
    def __init__(self, items: List[Tuple[Path, int]], tf):
        self.items = items
        self.tf = tf

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        path, label = self.items[idx]
        img = load_rgb_image(path)
        return self.tf(img), label


def _gather(folder: Path) -> List[Path]:
    return gather_images(folder)


def _class_image_paths(root: Path) -> List[Tuple[str, Path]]:
    if not root.exists():
        return []
    items: List[Tuple[str, Path]] = []
    for class_dir in sorted(root.iterdir()):
        if not class_dir.is_dir():
            continue
        for path in class_dir.rglob("*"):
            if path.is_file() and is_image_path(path):
                items.append((class_dir.name, path))
    return items


def _stratified_split(
    items: List[Tuple[Path, int]], val_frac: float, seed: int
) -> Tuple[List[Tuple[Path, int]], List[Tuple[Path, int]]]:
    by_label: Dict[int, List[Tuple[Path, int]]] = defaultdict(list)
    for item in items:
        by_label[item[1]].append(item)
    rng = random.Random(seed)
    train_items: List[Tuple[Path, int]] = []
    val_items: List[Tuple[Path, int]] = []
    for label_items in by_label.values():
        rng.shuffle(label_items)
        if len(label_items) <= 4:
            train_items.extend(label_items)
            continue
        n_val = max(1, int(len(label_items) * val_frac))
        val_items.extend(label_items[:n_val])
        train_items.extend(label_items[n_val:])
    return train_items, val_items


def _items_from_imagefolder_root(
    root: Path, registry: LabelRegistry, source: str
) -> List[Tuple[Path, int]]:
    items: List[Tuple[Path, int]] = []
    for raw_class, path in _class_image_paths(root):
        label = registry.label_for(raw_class, source)
        if label is not None:
            items.append((path, label))
    return items


def _plantvillage_class_names() -> List[str]:
    if config.DISEASE_TRAIN.exists():
        return sorted(p.name for p in config.DISEASE_TRAIN.iterdir() if p.is_dir())
    if config.PLANTVILLAGE_RAW.exists():
        return sorted(p.name for p in config.PLANTVILLAGE_RAW.iterdir() if p.is_dir())
    return []


# --------------------------------------------------------------------------- #
# Stage 2 - disease
# --------------------------------------------------------------------------- #
def _plantvillage_only_loaders(
    input_size: int, batch: int
) -> Tuple[DataLoader, DataLoader, List[str]]:
    train_root = config.PLANTVILLAGE_AUG_TRAIN if config.PLANTVILLAGE_AUG_TRAIN.exists() else config.UNIFIED_TRAIN
    valid_root = config.PLANTVILLAGE_AUG_VALID if config.PLANTVILLAGE_AUG_VALID.exists() else config.UNIFIED_VALID
    train_ds = ImageFolder(str(train_root), build_transforms(input_size, True))
    valid_ds = ImageFolder(str(valid_root), build_transforms(input_size, False))
    class_names = train_ds.classes
    train_dl = DataLoader(
        train_ds,
        **_dataloader_kwargs(shuffle=True, batch=batch, drop_last=True),
    )
    valid_dl = DataLoader(
        valid_ds,
        **_dataloader_kwargs(shuffle=False, batch=batch),
    )
    return train_dl, valid_dl, class_names


def _combined_disease_items() -> Tuple[List[Tuple[Path, int]], List[Tuple[Path, int]], LabelRegistry, Dict[str, int]]:
    pv_names = _plantvillage_class_names()
    registry = LabelRegistry(pv_names)
    train_items: List[Tuple[Path, int]] = []
    val_items: List[Tuple[Path, int]] = []
    counts: Dict[str, int] = defaultdict(int)

    def add_train(root: Path, source: str, name: str) -> None:
        items = _items_from_imagefolder_root(root, registry, source)
        train_items.extend(items)
        counts[name] += len(items)

    def add_val(root: Path, source: str, name: str) -> None:
        items = _items_from_imagefolder_root(root, registry, source)
        val_items.extend(items)
        counts[name] += len(items)

    def add_split(root: Path, source: str, name: str, val_frac: float = 0.1) -> None:
        items = _items_from_imagefolder_root(root, registry, source)
        tr, va = _stratified_split(items, val_frac, config.SEED)
        train_items.extend(tr)
        val_items.extend(va)
        counts[name] += len(items)

    # PlantVillage augmented (pre-split train/valid).
    if config.DISEASE_TRAIN.exists():
        add_train(config.DISEASE_TRAIN, "plantvillage", "plantvillage_aug_train")
    if config.DISEASE_VALID.exists():
        add_val(config.DISEASE_VALID, "plantvillage", "plantvillage_aug_valid")

    # Original PlantVillage (no valid split — hold out 10%).
    if config.PLANTVILLAGE_RAW.exists():
        add_split(config.PLANTVILLAGE_RAW, "plantvillage", "plantvillage_raw")

    # Bangladesh crop disease (exported ImageFolder).
    bd_train = config.BD_EXPORT_DIR / "train"
    bd_valid = config.BD_EXPORT_DIR / "valid"
    bd_test = config.BD_EXPORT_DIR / "test"
    if bd_train.exists():
        add_train(bd_train, "bd", "bd_train")
    if bd_valid.exists():
        add_val(bd_valid, "bd", "bd_valid")
    if bd_test.exists():
        add_val(bd_test, "bd", "bd_test")

    # PlantDoc (train + test as validation).
    pd_train = config.PLANTDOC_ROOT / "train"
    pd_test = config.PLANTDOC_ROOT / "test"
    if pd_train.exists():
        add_train(pd_train, "plantdoc", "plantdoc_train")
    if pd_test.exists():
        add_val(pd_test, "plantdoc", "plantdoc_test")

    # Regional archive subset (hold out 10%).
    if config.ARCHIVE_DISEASE.exists():
        archive_items = []
        for raw_class, path in _class_image_paths(config.ARCHIVE_DISEASE):
            if raw_class.lower() == "invalid":
                continue
            label = registry.label_for(raw_class, "archive")
            if label is not None:
                archive_items.append((path, label))
        tr, va = _stratified_split(archive_items, 0.1, config.SEED + 1)
        train_items.extend(tr)
        val_items.extend(va)
        counts["archive"] += len(archive_items)

    # Bangladeshi mango variety dataset (hold out 10%).
    if config.MANGIFERA_ROOT.exists():
        add_split(config.MANGIFERA_ROOT, "mangifera", "mangifera")

    # Bangladeshi Leaf Disease Detection Dataset (Bean / Corn / Red-Amaranth).
    try:
        bd_leaf_root = ensure_bd_leaf_extracted()
        if bd_leaf_root.exists():
            add_split(bd_leaf_root, "bd_leaf", "bd_leaf_disease")
    except FileNotFoundError as exc:
        print(f"Note: skipping bd_leaf_disease — {exc}")

    rng = random.Random(config.SEED)
    rng.shuffle(train_items)
    rng.shuffle(val_items)
    return train_items, val_items, registry, dict(counts)


class DiseaseImageFolder(ImageFolder):
    """Disease ImageFolder: skip mango-variety folders (those are Level 2 only)."""

    def __init__(self, root, transform=None, target_transform=None, is_valid_file=None):
        super().__init__(
            root,
            transform=transform,
            target_transform=target_transform,
            loader=_folder_image_loader,
            is_valid_file=is_valid_file,
        )

    @staticmethod
    def find_classes(directory):
        names = [p.name for p in Path(directory).iterdir() if p.is_dir()]
        skip = set()
        for name in names:
            canon = merge_class_name(name)
            if canon != name and (Path(directory) / canon).is_dir():
                skip.add(name)
        classes = sorted(
            n for n in names if n not in skip and not is_variety_class(n)
        )
        if not classes:
            raise FileNotFoundError(f"No disease class folders in {directory}")
        return classes, {c: i for i, c in enumerate(classes)}


def class_weights_for_dataset(ds) -> Optional[torch.Tensor]:
    """Inverse-sqrt class weights for focal / CE (D)."""
    if not hasattr(ds, "targets") or not hasattr(ds, "classes"):
        return None
    counts = np.bincount(ds.targets, minlength=len(ds.classes)).astype(np.float64)
    w = 1.0 / np.sqrt(np.maximum(counts, 1.0))
    w = w / max(w.mean(), 1e-8)
    return torch.tensor(w, dtype=torch.float32)


def _make_loader(ds, batch: int, *, train: bool) -> DataLoader:
    if train and config.USE_BALANCED_SAMPLER and hasattr(ds, "targets"):
        counts = np.bincount(ds.targets, minlength=len(ds.classes)).astype(np.float64)
        w_class = 1.0 / np.sqrt(np.maximum(counts, 1.0))
        sample_w = [float(w_class[t]) for t in ds.targets]
        sampler = WeightedRandomSampler(sample_w, num_samples=len(sample_w), replacement=True)
        kw = _dataloader_kwargs(shuffle=False, batch=batch, drop_last=True)
        kw["sampler"] = sampler
        return DataLoader(ds, **kw)
    return DataLoader(
        ds,
        **_dataloader_kwargs(shuffle=train, batch=batch, drop_last=train),
    )


def _unified_split_loaders(
    input_size: int, batch: int
) -> Tuple[DataLoader, DataLoader, List[str]]:
    """Load Datasets/{train,valid} ImageFolders (merged classes, no varieties)."""
    train_ds = DiseaseImageFolder(str(config.UNIFIED_TRAIN), build_transforms(input_size, True))
    valid_ds = DiseaseImageFolder(str(config.UNIFIED_VALID), build_transforms(input_size, False))
    print(f"Unified splits: {len(train_ds.classes)} disease classes")
    print(f"Train samples: {len(train_ds):,} | Val samples: {len(valid_ds):,}")
    return (
        _make_loader(train_ds, batch, train=True),
        _make_loader(valid_ds, batch, train=False),
        train_ds.classes,
    )


def crop_loaders(input_size: int, batch: int) -> Tuple[DataLoader, DataLoader, List[str]]:
    """Level-2 leaf-type (crop) ImageFolders."""
    if not config._split_has_classes(config.CROP_TRAIN):
        raise FileNotFoundError(
            f"Leaf-type dataset not found at {config.CROP_TRAIN}. "
            "Run: powershell -File scripts/build_leaf_type.ps1"
        )
    train_ds = ImageFolder(str(config.CROP_TRAIN), build_transforms(input_size, True))
    valid_ds = ImageFolder(str(config.CROP_VALID), build_transforms(input_size, False))
    print(f"Leaf-type crops: {len(train_ds.classes)} | train={len(train_ds):,} val={len(valid_ds):,}")
    return (
        _make_loader(train_ds, batch, train=True),
        _make_loader(valid_ds, batch, train=False),
        train_ds.classes,
    )


def combined_disease_loaders(
    input_size: int, batch: int
) -> Tuple[DataLoader, DataLoader, List[str]]:
    if config._split_has_classes(config.UNIFIED_TRAIN) and config._split_has_classes(config.UNIFIED_VALID):
        return _unified_split_loaders(input_size, batch)

    train_items, val_items, registry, counts = _combined_disease_items()
    if not train_items:
        raise FileNotFoundError(
            "No disease training images found under Datasets/. "
            "Check that at least one disease dataset folder exists."
        )

    summarize_registry(registry, counts)
    class_names = registry.class_names
    print(f"Train samples: {len(train_items):,} | Val samples: {len(val_items):,}")

    train_ds = ImageListDataset(train_items, build_transforms(input_size, True))
    val_ds = ImageListDataset(val_items, build_transforms(input_size, False))
    train_dl = DataLoader(
        train_ds,
        **_dataloader_kwargs(shuffle=True, batch=batch, drop_last=True),
    )
    val_dl = DataLoader(
        val_ds,
        **_dataloader_kwargs(shuffle=False, batch=batch),
    )
    return train_dl, val_dl, class_names


def disease_loaders(
    input_size: int,
    batch: int,
    source: Optional[str] = None,
) -> Tuple[DataLoader, DataLoader, List[str]]:
    mode = (source or config.DEFAULT_DISEASE_SOURCE).lower()
    if mode == "plantvillage":
        return _plantvillage_only_loaders(input_size, batch)
    if mode == "combined":
        return combined_disease_loaders(input_size, batch)
    if mode == "bd":
        train_root = config.BD_EXPORT_DIR / "train"
        valid_root = config.BD_EXPORT_DIR / "valid"
        if not train_root.exists():
            raise FileNotFoundError(
                f"Bangladesh dataset not found at {train_root}. "
                "Run: python download_bd_dataset.py"
            )
        train_ds = ImageFolder(str(train_root), build_transforms(input_size, True))
        valid_ds = ImageFolder(str(valid_root), build_transforms(input_size, False))
        train_dl = DataLoader(
            train_ds,
            **_dataloader_kwargs(shuffle=True, batch=batch, drop_last=True),
        )
        valid_dl = DataLoader(
            valid_ds,
            **_dataloader_kwargs(shuffle=False, batch=batch),
        )
        return train_dl, valid_dl, train_ds.classes
    raise ValueError(f"Unknown disease source: {mode!r}. Use plantvillage | bd | combined.")


def disease_image_paths_for_leaf_gate() -> List[Path]:
    """Collect plant/leaf images from all disease datasets for the leaf gate."""
    paths: List[Path] = []
    seen: set[str] = set()

    def add_root(root: Path) -> None:
        if not root.exists():
            return
        for _, path in _class_image_paths(root):
            key = str(path.resolve()).lower()
            if key not in seen:
                seen.add(key)
                paths.append(path)

    if config._split_has_classes(config.UNIFIED_TRAIN):
        add_root(config.UNIFIED_TRAIN)
        add_root(config.UNIFIED_VALID)
        add_root(config.UNIFIED_TEST)
        return paths

    add_root(config.PLANTVILLAGE_AUG_TRAIN)
    add_root(config.PLANTVILLAGE_AUG_VALID)
    add_root(config.PLANTVILLAGE_RAW)
    add_root(config.BD_EXPORT_DIR / "train")
    add_root(config.BD_EXPORT_DIR / "valid")
    add_root(config.BD_EXPORT_DIR / "test")
    add_root(config.PLANTDOC_ROOT / "train")
    add_root(config.PLANTDOC_ROOT / "test")
    if config.ARCHIVE_DISEASE.exists():
        for raw_class, path in _class_image_paths(config.ARCHIVE_DISEASE):
            if raw_class.lower() == "invalid":
                continue
            key = str(path.resolve()).lower()
            if key not in seen:
                seen.add(key)
                paths.append(path)
    add_root(config.MANGIFERA_ROOT)
    try:
        add_root(ensure_bd_leaf_extracted())
    except FileNotFoundError:
        pass
    return paths


# --------------------------------------------------------------------------- #
# Stage 1 - leaf gate
# --------------------------------------------------------------------------- #
def _leaf_items() -> Tuple[List[Tuple[Path, int]], List[str]]:
    """class_names = ['leaf', 'non_leaf']; leaf=0, non_leaf=1."""
    class_names = ["leaf", "non_leaf"]
    leaf_root = config.LEAF_SPLIT_TRAIN / "leaf"
    if not leaf_root.is_dir():
        leaf_root = config.LEAF_DATA / "leaf"
    leaf = [(p, 0) for p in _gather(leaf_root)]

    if config.LEAF_USE_DISEASE_IMAGES:
        leaf += [(p, 0) for p in disease_image_paths_for_leaf_gate()]

    non_leaf_root = config.LEAF_SPLIT_TRAIN / "non_leaf"
    if not non_leaf_root.is_dir():
        non_leaf_root = config.LEAF_DATA / "non_leaf"
    non_leaf_paths = list(_gather(non_leaf_root))
    for extra in config.EXTRA_NON_LEAF:
        non_leaf_paths += _gather(extra)
    if config.ARCHIVE_INVALID.exists():
        non_leaf_paths += _gather(config.ARCHIVE_INVALID)

    rng = random.Random(config.SEED)
    rng.shuffle(non_leaf_paths)
    cap = int(len(leaf) * config.LEAF_NON_LEAF_RATIO)
    non_leaf = [(p, 1) for p in non_leaf_paths[:cap]]
    return leaf + non_leaf, class_names


def leaf_loaders(input_size: int, batch: int, val_frac: float = 0.1):
    if (config.LEAF_SPLIT_TRAIN / "leaf").is_dir() and (config.LEAF_SPLIT_VALID / "leaf").is_dir():
        train_ds = ImageFolder(str(config.LEAF_SPLIT_TRAIN), build_transforms(input_size, True))
        val_ds = ImageFolder(str(config.LEAF_SPLIT_VALID), build_transforms(input_size, False))
        print(
            f"Leaf gate splits: {train_ds.classes} | "
            f"{len(train_ds):,} train / {len(val_ds):,} val"
        )
        train_dl = DataLoader(
            train_ds,
            **_dataloader_kwargs(shuffle=True, batch=batch, drop_last=True),
        )
        val_dl = DataLoader(
            val_ds,
            **_dataloader_kwargs(shuffle=False, batch=batch),
        )
        return train_dl, val_dl, train_ds.classes

    items, class_names = _leaf_items()
    rng = random.Random(config.SEED)
    rng.shuffle(items)
    n_val = int(len(items) * val_frac)
    val_items, train_items = items[:n_val], items[n_val:]

    print(
        f"Leaf gate: {len(train_items):,} train / {len(val_items):,} val "
        f"(leaf={sum(1 for _, y in items if y == 0):,}, "
        f"non_leaf={sum(1 for _, y in items if y == 1):,})"
    )

    train_ds = ImageListDataset(train_items, build_transforms(input_size, True))
    val_ds = ImageListDataset(val_items, build_transforms(input_size, False))
    train_dl = DataLoader(
        train_ds,
        **_dataloader_kwargs(shuffle=True, batch=batch, drop_last=True),
    )
    val_dl = DataLoader(
        val_ds,
        **_dataloader_kwargs(shuffle=False, batch=batch),
    )
    return train_dl, val_dl, class_names
