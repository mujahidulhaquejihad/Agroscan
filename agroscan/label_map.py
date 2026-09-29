"""Normalize class names across heterogeneous plant-disease datasets."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

# PlantDoc folder name -> PlantVillage-style canonical name (when known).
PLANTDOC_TO_CANONICAL: Dict[str, str] = {
    "Apple Scab Leaf": "Apple___Apple_scab",
    "Apple leaf": "Apple___healthy",
    "Bell_pepper leaf spot": "Pepper,_bell___Bacterial_spot",
    "Bell_pepper leaf": "Pepper,_bell___healthy",
    "Blueberry leaf": "Blueberry___healthy",
    "Cherry leaf": "Cherry_(including_sour)___healthy",
    "Corn Gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn rust leaf": "Corn_(maize)___Common_rust_",
    "Grape leaf": "Grape___healthy",
    "Grape leaf black rot": "Grape___Black_rot",
    "Peach leaf": "Peach___healthy",
    "Potato leaf early blight": "Potato___Early_blight",
    "Potato leaf late blight": "Potato___Late_blight",
    "Potato leaf": "Potato___healthy",
    "Raspberry leaf": "Raspberry___healthy",
    "Soyabean leaf": "Soybean___healthy",
    "Soybean leaf": "Soybean___healthy",
    "Squash Powdery mildew leaf": "Squash___Powdery_mildew",
    "Strawberry leaf": "Strawberry___healthy",
    "Tomato Early blight leaf": "Tomato___Early_blight",
    "Tomato Septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "Tomato leaf": "Tomato___healthy",
    "Tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "Tomato leaf late blight": "Tomato___Late_blight",
    "Tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "Tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato mold leaf": "Tomato___Late_blight",
    "Tomato two spotted spider mites leaf": "Tomato___Spider_mites Two-spotted_spider_mite",
    "grape leaf black rot": "Grape___Black_rot",
}

# Archive folder names (typo DIsease) -> canonical.
ARCHIVE_TO_CANONICAL: Dict[str, str] = {
    "Corn___Common_Rust": "Corn_(maize)___Common_rust_",
    "Corn___Gray_Leaf_Spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___Healthy": "Corn_(maize)___healthy",
    "Corn___Leaf_Blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Potato___Early_Blight": "Potato___Early_blight",
    "Potato___Healthy": "Potato___healthy",
    "Potato___Late_Blight": "Potato___Late_blight",
    "Rice___Brown_Spot": "Rice___Brown_spot",
    "Rice___Healthy": "Rice___healthy",
    "Rice___Hispa": "Rice___Hispa",
    "Rice___Leaf_Blast": "Rice___Leaf_blast",
    "Wheat___Brown_Rust": "Wheat___Brown_rust",
    "Wheat___Healthy": "Wheat___healthy",
    "Wheat___Yellow_Rust": "Wheat___Yellow_rust",
}

# Duplicate / overlapping folder names already in Datasets/{train,valid,test}.
MERGE_ALIASES: Dict[str, str] = {
    "Apple rust leaf": "Apple___Cedar_apple_rust",
    "Corn___Blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn___Common_Rust": "Corn_(maize)___Common_rust_",
    "Corn___Gray_Leaf_Spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___healthy": "Corn_(maize)___healthy",
    "Rice___Brownspot": "Rice___Brown_spot",
    "Rice___Leaf_blast": "Rice___Blast",
    "Tomato___Spider_Mites_Two-spotted_Spider_Mite": "Tomato___Spider_mites Two-spotted_spider_mite",
    "Potato___Healthy_Potatoes": "Potato___healthy",
}


def merge_class_name(name: str) -> str:
    """Collapse known duplicate labels onto one canonical folder name."""
    name = (name or "").strip()
    return MERGE_ALIASES.get(name, name)


def is_variety_class(name: str) -> bool:
    return "variety" in (name or "").lower()


def is_other_crop(crop: Optional[str]) -> bool:
    """True when Level-2 is the out-of-set 'Other' class (not a trained crop)."""
    return (crop or "").strip().lower() in {"other", "unknown", "none", "n/a"}


def crop_from_class(name: str) -> str:
    """Level-2 leaf type: crop/plant name from a disease class folder."""
    name = merge_class_name(name)
    crop = name.split("___", 1)[0] if "___" in name else name
    crop = crop.replace("_(maize)", "").replace("(maize)", "")
    crop = crop.replace("_(including_sour)", "").replace(",_bell", "")
    low = crop.lower().replace("_", " ").strip()
    if low.startswith("corn"):
        return "Corn"
    if low.startswith("pepper"):
        return "Pepper"
    if low.startswith("cherry"):
        return "Cherry"
    if "amaranth" in low:
        return "Red Amaranth"
    return crop.replace("_", " ").strip() or name


def classes_for_crop(class_names: Iterable[str], crop: str) -> List[int]:
    """Indices of Level-3 classes that belong to a Level-2 crop."""
    if is_other_crop(crop):
        return []
    want = (crop or "").strip().lower()
    hits = [i for i, n in enumerate(class_names) if crop_from_class(n).lower() == want]
    if hits:
        return hits
    return list(range(len(list(class_names))))


def merge_key(name: str) -> str:
    """Loose key for grouping semantically similar labels across datasets."""
    s = name.replace("___", " ").replace("__", " ")
    s = re.sub(r"[_\-\(\),\.]", " ", s.lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    for token in (
        "leaf",
        "leaves",
        "images",
        "image",
        "normal",
        "healthy",
        "disease",
        "variety",
        "mango",
    ):
        s = re.sub(rf"\b{token}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or name.lower()


def _bd_to_canonical(raw: str) -> str:
    """Bangladesh labels like Rice_Blast -> Rice___Blast."""
    if "___" in raw:
        return raw
    parts = raw.split("_", 1)
    if len(parts) == 2:
        crop, cond = parts
        if cond.lower() in ("normal", "healthy"):
            return f"{crop}___healthy"
        return f"{crop}___{cond}"
    return raw.replace("_", "___", 1) if "_" in raw else raw


def _mango_variety_to_canonical(folder_name: str) -> str:
    """Mangifera2012 variety folder -> Mango___Variety_<name>."""
    base = re.sub(r"-\d+$", "", folder_name).replace("-", " ").strip()
    slug = base.replace(" ", "_")
    return f"Mango___Variety_{slug}"


def _bd_leaf_to_canonical(raw: str) -> str:
    """Bangladeshi leaf disease zip classes: Bean, Corn, Red-Amaranth."""
    crop = raw.replace("-", "_").replace(" ", "_").strip()
    if crop.lower() == "corn":
        crop = "Corn_(maize)"
    return f"{crop}___BD_Leaf_Disease"


def canonical_name(raw: str, source: str, plantvillage_names: Optional[Set[str]] = None) -> str:
    """Map a raw folder/class name to a stable canonical label."""
    raw = raw.strip()
    if not raw or raw.lower() == "invalid":
        return ""

    if source == "plantdoc":
        if raw in PLANTDOC_TO_CANONICAL:
            return PLANTDOC_TO_CANONICAL[raw]
    if source == "archive":
        if raw in ARCHIVE_TO_CANONICAL:
            return ARCHIVE_TO_CANONICAL[raw]
        if raw.lower() == "invalid":
            return ""
    if source == "bd":
        return _bd_to_canonical(raw)
    if source == "mangifera":
        return _mango_variety_to_canonical(raw)
    if source == "bd_leaf":
        return _bd_leaf_to_canonical(raw)

    # PlantVillage-style names pass through.
    if "___" in raw:
        return raw

    # Try to align underscore labels with a known PlantVillage class.
    if plantvillage_names:
        candidate = _bd_to_canonical(raw)
        if candidate in plantvillage_names:
            return candidate
        key = merge_key(raw)
        for pv in plantvillage_names:
            if merge_key(pv) == key:
                return pv

    return _bd_to_canonical(raw)


class LabelRegistry:
    """Assign integer labels to canonical class names discovered from all sources."""

    def __init__(self, plantvillage_names: Optional[Iterable[str]] = None):
        self._pv: Set[str] = set(plantvillage_names or [])
        self._canonical: List[str] = []
        self._index: Dict[str, int] = {}
        self._merge_to_canonical: Dict[str, str] = {}

    @property
    def class_names(self) -> List[str]:
        return list(self._canonical)

    def register(self, raw_name: str, source: str) -> Optional[int]:
        name = canonical_name(raw_name, source, self._pv)
        if not name:
            return None
        if name not in self._index:
            self._index[name] = len(self._canonical)
            self._canonical.append(name)
        self._merge_to_canonical[merge_key(name)] = name
        return self._index[name]

    def label_for(self, raw_name: str, source: str) -> Optional[int]:
        return self.register(raw_name, source)


def summarize_registry(registry: LabelRegistry, counts: Dict[str, int]) -> None:
    """Print per-source image counts (counts keys are source names)."""
    total = sum(counts.values())
    print(f"Unified disease classes: {len(registry.class_names)}")
    print(f"Total indexed images: {total:,}")
    for src, n in sorted(counts.items()):
        if n:
            print(f"  {src:>14}: {n:>8,} images")
