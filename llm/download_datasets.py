"""Download agriculture LLM training sources into Datasets/llm/.

Run:
  python -m llm.download_datasets

Creates:
  Datasets/llm/raw/          extracted local zips + HF exports
  Datasets/llm/SOURCES.md    what was downloaded
"""
from __future__ import annotations

import csv
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "Datasets"
LLM = DATASETS / "llm"
RAW = LLM / "raw"
HF_DIR = RAW / "huggingface"
ZIPS = DATASETS / "sources" / "zips"
CROPS = DATASETS / "tabular" / "crops"


def _ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    HF_DIR.mkdir(parents=True, exist_ok=True)
    CROPS.mkdir(parents=True, exist_ok=True)
    ZIPS.mkdir(parents=True, exist_ok=True)


def extract_local_zips() -> list[str]:
    notes = []
    # Crop recommendation small CSV
    z1 = ZIPS / "Appropriate Crop Recommendation Dataset for Cultiv.zip"
    if z1.exists():
        with zipfile.ZipFile(z1) as z:
            z.extractall(RAW / "crop_rec_bd")
        src = RAW / "crop_rec_bd" / "Appropriate Crop Recommendation Dataset for Cultiv" / "final_crops_data.csv"
        if src.exists():
            dest = CROPS / "final_crops_data.csv"
            shutil.copy2(src, dest)
            notes.append(f"Extracted crop rec CSV -> {dest}")

    z2 = ZIPS / "archive.zip"
    if z2.exists():
        with zipfile.ZipFile(z2) as z:
            z.extractall(RAW / "bd_crop_50k")
        src = RAW / "bd_crop_50k" / "Bangladesh_Crop_Dataset-50k.csv"
        if src.exists():
            dest = CROPS / "Bangladesh_Crop_Dataset-50k.csv"
            shutil.copy2(src, dest)
            # Also keep a light sample for QA building (full 50k is fine as CSV)
            notes.append(f"Extracted BD crop 50k CSV -> {dest} ({dest.stat().st_size} bytes)")

    # Skip ScienceDirect medical PDFs and district GeoTIFF zip for LLM text training
    notes.append("Skipped ScienceDirect medical PDF zip (not agri advisory text).")
    notes.append("Skipped Barisal/Dinajpur/Rangpur GeoTIFF zip (imagery, not Q&A text).")
    return notes


def _save_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def download_krishokchat(max_rows: int = 80000) -> list[str]:
    """Bengali citation-grounded agri instruction data (best BD source)."""
    notes = []
    try:
        from datasets import load_dataset
    except ImportError:
        return ["datasets package missing — pip install datasets"]

    out = HF_DIR / "krishokchat"
    out.mkdir(parents=True, exist_ok=True)
    try:
        # Prefer SFT chat splits if available; else flat default
        try:
            ds = load_dataset("RaiyanKhaan/KrishokChat-145k", name="splits")
            split_name = "train" if "train" in ds else list(ds.keys())[0]
            data = ds[split_name]
            notes.append(f"Loaded KrishokChat splits/{split_name}: {len(data)} rows")
            rows = []
            for i, ex in enumerate(data):
                if i >= max_rows:
                    break
                # chat messages format
                msgs = ex.get("messages") or ex.get("conversations")
                if msgs:
                    # flatten to instruction/output
                    user = ""
                    assistant = ""
                    for m in msgs:
                        role = (m.get("role") or m.get("from") or "").lower()
                        content = m.get("content") or m.get("value") or ""
                        if role in ("user", "human"):
                            user = content
                        elif role in ("assistant", "gpt"):
                            assistant = content
                    if user and assistant:
                        rows.append(
                            {
                                "instruction": user,
                                "input": "",
                                "output": assistant,
                                "source": "krishokchat_splits",
                            }
                        )
                else:
                    q = ex.get("question") or ex.get("instruction") or ""
                    a = ex.get("answer") or ex.get("output") or ""
                    if q and a:
                        rows.append(
                            {
                                "instruction": q,
                                "input": "",
                                "output": a,
                                "source": "krishokchat_splits",
                            }
                        )
            _save_jsonl(out / "qa.jsonl", rows)
            notes.append(f"Wrote {len(rows)} KrishokChat QA -> {out / 'qa.jsonl'}")
            return notes
        except Exception as e_split:
            notes.append(f"splits config failed ({e_split}); trying default…")

        ds = load_dataset("RaiyanKhaan/KrishokChat-145k")
        split = ds["train"] if "train" in ds else ds[list(ds.keys())[0]]
        notes.append(f"Loaded KrishokChat default: {len(split)} rows")
        rows = []
        for i, ex in enumerate(split):
            if i >= max_rows:
                break
            q = (ex.get("question") or "").strip()
            a = (ex.get("answer") or "").strip()
            if not q or not a:
                continue
            # Strip oversized citation blocks a bit for small models
            if "Source |" in a and len(a) > 1200:
                a = a.split("Source |")[0].strip() + "\n(Source: BARI/BRRI/DAE manuals via KrishokChat)"
            rows.append(
                {
                    "instruction": q,
                    "input": "",
                    "output": a,
                    "source": "krishokchat",
                    "crop": ex.get("crop"),
                }
            )
        _save_jsonl(out / "qa.jsonl", rows)
        notes.append(f"Wrote {len(rows)} KrishokChat QA -> {out / 'qa.jsonl'}")

        # Also try knowledge_nodes + benchmark if present
        for cfg in ("knowledge_nodes", "benchmark"):
            try:
                kn = load_dataset("RaiyanKhaan/KrishokChat-145k", name=cfg)
                part = kn[list(kn.keys())[0]]
                part.to_json(str(out / f"{cfg}.jsonl"), force_ascii=False)
                notes.append(f"Saved config {cfg}: {len(part)} rows")
            except Exception as e:
                notes.append(f"Optional config {cfg} skipped: {e}")
    except Exception as e:
        notes.append(f"FAILED KrishokChat download: {e}")
    return notes


def download_english_agri_qa(max_rows: int = 15000) -> list[str]:
    """Extra English agri Q&A if available on HF."""
    notes = []
    try:
        from datasets import load_dataset
    except ImportError:
        return []

    candidates = [
        ("KisanVaani/agriculture-qa", None),
        ("ajibawa-2023/Agriculture-Knowledge", None),
    ]
    out = HF_DIR / "english_agri_qa"
    out.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []

    for name, config in candidates:
        try:
            ds = load_dataset(name, name=config) if config else load_dataset(name)
            split = ds["train"] if "train" in ds else ds[list(ds.keys())[0]]
            n = 0
            for ex in split:
                if n >= max_rows // len(candidates):
                    break
                q = (
                    ex.get("question")
                    or ex.get("instruction")
                    or ex.get("input")
                    or ex.get("query")
                    or ""
                )
                a = ex.get("answer") or ex.get("output") or ex.get("response") or ""
                q, a = str(q).strip(), str(a).strip()
                if len(q) < 8 or len(a) < 8:
                    continue
                all_rows.append(
                    {
                        "instruction": q,
                        "input": "",
                        "output": a[:2000],
                        "source": name,
                    }
                )
                n += 1
            notes.append(f"Loaded {name}: +{n} rows")
        except Exception as e:
            notes.append(f"Skip {name}: {e}")

    if all_rows:
        _save_jsonl(out / "qa.jsonl", all_rows)
        notes.append(f"Wrote {len(all_rows)} EN agri QA -> {out / 'qa.jsonl'}")
    return notes


def download_crop_rec_classic() -> list[str]:
    """Classic NPK crop recommendation CSV (used for synthetic climate→crop QA)."""
    notes = []
    try:
        from datasets import load_dataset
    except ImportError:
        return []
    out = HF_DIR / "crop_recommendation"
    out.mkdir(parents=True, exist_ok=True)
    for name in (
        "siddharthss/crop-recommendation-dataset",
        "atharvjairath/crop-recommendation",
    ):
        try:
            ds = load_dataset(name)
            split = ds["train"] if "train" in ds else ds[list(ds.keys())[0]]
            path = out / "crop_recommendation.csv"
            split.to_csv(str(path))
            # also copy into Datasets/tabular/crops
            dest = CROPS / "crop_recommendation_classic.csv"
            shutil.copy2(path, dest)
            notes.append(f"Downloaded {name} -> {dest} ({len(split)} rows)")
            return notes
        except Exception as e:
            notes.append(f"Skip {name}: {e}")
    return notes


def write_sources_md(notes: list[str]) -> None:
    path = LLM / "SOURCES.md"
    path.write_text(
        "# LLM data sources\n\n"
        + "\n".join(f"- {n}" for n in notes)
        + "\n\nRegenerate Q&A with:\n\n```\npython -m llm.build_qa_dataset\n```\n",
        encoding="utf-8",
    )


def main() -> None:
    _ensure_dirs()
    notes: list[str] = []
    print("Extracting local zips…")
    notes.extend(extract_local_zips())
    print("Downloading KrishokChat-145k (Bengali agri — primary)…")
    notes.extend(download_krishokchat(max_rows=80000))
    print("Downloading English agri QA (optional)…")
    notes.extend(download_english_agri_qa(max_rows=12000))
    print("Downloading classic crop recommendation CSV…")
    notes.extend(download_crop_rec_classic())
    write_sources_md(notes)
    print("\n=== DONE ===")
    for n in notes:
        print("-", n)
    print(f"\nSee {LLM / 'SOURCES.md'}")


if __name__ == "__main__":
    main()
