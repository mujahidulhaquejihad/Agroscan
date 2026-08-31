"""Central configuration: dataset paths, model list, hyperparameters."""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
# Training images/QA: Datasets/    Runtime pack+DBs: data/    Checkpoints: models/    LoRA: llm_data/
DATASETS = ROOT / "Datasets"
VISION = DATASETS / "vision"  # optional source dumps; live splits are leaf_gate / leaf_type / train|valid|test
DISEASE_DIR = VISION / "disease"
LEAF_GATE_DIR = DATASETS / "leaf_gate"
CROP_DIR = DATASETS / "leaf_type"
TABULAR = DATASETS / "tabular"
CROPS_DIR = TABULAR / "crops"
LLM_DATA = DATASETS / "llm"
SOURCES = DATASETS / "sources"
MODELS_DIR = ROOT / "models"
LLM_ADAPTERS = ROOT / "llm_data" / "adapters"
DATA_DIR = ROOT / "data"
SHOP_DB_PATH = DATA_DIR / "agrovet_shop.db"
AGROSCAN_PACK_DIR = DATA_DIR / "agroscan"
MODELS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Stage 1 - leaf vs non-leaf gate (Datasets/leaf_gate/{train,valid,test})
LEAF_SPLIT_TRAIN = LEAF_GATE_DIR / "train"
LEAF_SPLIT_VALID = LEAF_GATE_DIR / "valid"
LEAF_SPLIT_TEST = LEAF_GATE_DIR / "test"
LEAF_DATA = LEAF_SPLIT_TRAIN
EXTRA_NON_LEAF: list[Path] = []

# Stage 2 - crop / leaf-type (Datasets/leaf_type/{train,valid,test})
CROP_TRAIN = CROP_DIR / "train"
CROP_VALID = CROP_DIR / "valid"
CROP_TEST = CROP_DIR / "test"
CROP_ARCH = "efficientnet_b3"
CROP_EPOCHS = 6
CROP_BATCH = 32
CROP_LR = 1e-3

# Stage 3 - unified disease splits: Datasets/{train,valid,test}/<class>/
DISEASE_TRAIN = DATASETS / "train"
DISEASE_VALID = DATASETS / "valid"
DISEASE_TEST = DATASETS / "test"
UNIFIED_TRAIN = DISEASE_TRAIN
UNIFIED_VALID = DISEASE_VALID
UNIFIED_TEST = DISEASE_TEST


def _split_has_classes(root: Path) -> bool:
    return root.is_dir() and any(p.is_dir() for p in root.iterdir())


# Optional source trees (only present if re-downloaded)
PLANTVILLAGE_AUG_TRAIN = (
    DISEASE_DIR
    / "plantvillage_augmented"
    / "New Plant Diseases Dataset(Augmented)"
    / "New Plant Diseases Dataset(Augmented)"
    / "train"
)
PLANTVILLAGE_AUG_VALID = PLANTVILLAGE_AUG_TRAIN.parent / "valid"
PLANTVILLAGE_RAW = DISEASE_DIR / "plantvillage_raw"
BD_EXPORT_DIR = DISEASE_DIR / "bd_crop_disease"
PLANTDOC_ROOT = DISEASE_DIR / "plantdoc"
ARCHIVE_DISEASE = DISEASE_DIR / "archive_crop_disease" / "CropDisease" / "Crop___DIsease"
MANGIFERA_ROOT = DISEASE_DIR / "mangifera2012" / "Mango_Dataset_2012"

# Bangladeshi Leaf Disease Detection Dataset (source zip + extracted images).
BD_LEAF_DATASET_DIR = SOURCES / "bangladeshi_leaf_disease"
BD_LEAF_EXPORT_DIR = DISEASE_DIR / "bd_leaf_disease"
BD_LEAF_ZIP = (
    BD_LEAF_DATASET_DIR
    / "Bangladeshi Leaf Disease Detection Dataset"
    / "Leaf Disease detection Dataset.zip"
)

# Tabular crop recommendation + farm planner
CROPS_CSV = CROPS_DIR / "final_crops_data.csv"
FLORA_TXT = LLM_DATA / "flora_raw.txt"

# Bangladesh multi-crop disease dataset (Hugging Face, gated).
# https://huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset
BD_HF_DATASET = "Saon110/bd-crop-vegetable-plant-disease-dataset"

# Extra non-leaf negatives for the leaf gate.
ARCHIVE_INVALID = ARCHIVE_DISEASE / "Invalid"

# Training data source: plantvillage | bd | combined
DEFAULT_DISEASE_SOURCE = "combined"
# Focal loss (D) + balanced sampling (C)
FOCAL_GAMMA = 2.0
USE_FOCAL_LOSS = True
USE_BALANCED_SAMPLER = True
LEAF_USE_DISEASE_IMAGES = True

# Checkpoint file names
LEAF_CKPT = MODELS_DIR / "leaf_gate.pt"
CROP_CKPT = MODELS_DIR / "leaf_type.pt"


def disease_ckpt(arch: str) -> Path:
    return MODELS_DIR / f"disease_{arch}.pt"


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
# Level-3 disease: run 3 backbones, pick highest-confidence model (no averaging).
DISEASE_ARCHS = ["efficientnet_b3", "resnet50", "densenet121"]

# Leaf gate uses a single fast backbone.
LEAF_ARCH = "mobilenet_v3_large"

# Cap non-leaf samples to this multiple of the leaf count (avoids the
# huge fashion set swamping the ~6.5k leaf images and biasing the gate).
LEAF_NON_LEAF_RATIO = 1.5

# Per-architecture input resolution (EfficientNet-B3 prefers 300px).
INPUT_SIZE = {
    "efficientnet_b3": 300,
    "resnet50": 224,
    "densenet121": 224,
    "mobilenet_v3_large": 224,
}
DEFAULT_INPUT_SIZE = 224

# ImageNet normalization (all backbones are pretrained on ImageNet).
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]

# --------------------------------------------------------------------------- #
# Training hyperparameters
# --------------------------------------------------------------------------- #
SEED = 42
# Each DataLoader worker imports torch + CUDA DLLs, which commit a lot of
# memory on Windows. With 16GB RAM + ~15GB pagefile, keep this small to avoid
# "[WinError 1455] paging file too small". Raise it only after enlarging the
# Windows pagefile (see README).
# 0 = load images in the main process (safest on Windows with large phone photos).
# Raise to 2–4 only after enlarging the pagefile if you want faster loading.
NUM_WORKERS = 0
PREFETCH_FACTOR = 2

LEAF_EPOCHS = 4
LEAF_BATCH = 64
LEAF_LR = 1e-3

DISEASE_EPOCHS = 6
DISEASE_BATCH = 32          # fits EfficientNet-B3 @300px on a 12GB RTX 3060
DISEASE_LR = 1e-3

# Confidence below which the disease prediction is flagged as "uncertain".
UNCERTAIN_THRESHOLD = 0.45
# Below this, the UI tells the user to retake a clearer photo or contact a vet.
LOW_CONFIDENCE_THRESHOLD = 0.80
# Leaf-gate probability above which an image is accepted as a leaf.
LEAF_ACCEPT_THRESHOLD = 0.5
# Level-2 crop confidence below which the user must pick from top-3 options.
CROP_USER_CONFIRM_THRESHOLD = 0.90

# Friendly names shown in the web UI and API responses.
MODEL_DISPLAY_NAMES = {
    "efficientnet_b3": "EfficientNet-B3",
    "resnet50": "ResNet-50",
    "mobilenet_v3_large": "MobileNetV3",
    "densenet121": "DenseNet-121",
}


def model_display_name(arch: str) -> str:
    return MODEL_DISPLAY_NAMES.get(arch, arch)
