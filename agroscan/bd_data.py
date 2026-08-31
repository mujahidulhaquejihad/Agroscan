"""Load the Bangladesh AgroScan data pack (JSON under data/agroscan/)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from agroscan.config import AGROSCAN_PACK_DIR


def _read(name: str):
    path = AGROSCAN_PACK_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def treatments() -> List[dict]:
    data = _read("disease_treatments.json")
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def treatments_by_class() -> Dict[str, dict]:
    return {str(r.get("class_name") or ""): r for r in treatments() if r.get("class_name")}


@lru_cache(maxsize=1)
def treatments_by_kb() -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for r in treatments():
        key = str(r.get("kb_key") or "")
        if not key:
            continue
        out.setdefault(key, []).append(r)
    return out


@lru_cache(maxsize=1)
def products() -> List[dict]:
    data = _read("products.json")
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def equipment() -> List[dict]:
    data = _read("equipment.json")
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def catalogue_by_sku() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for row in products() + equipment():
        sku = row.get("sku")
        if sku:
            out[str(sku)] = row
    return out


@lru_cache(maxsize=1)
def suppliers() -> List[dict]:
    data = _read("suppliers.json")
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def upazilas() -> List[dict]:
    data = _read("upazilas.json")
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def crops() -> List[dict]:
    data = _read("crop_profitability.json")
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def safety() -> dict:
    data = _read("regulatory_safety.json")
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def warning_boxes() -> Dict[str, dict]:
    boxes = safety().get("ui_warning_boxes") or []
    return {str(b.get("id")): b for b in boxes if b.get("id")}


def warning_box(box_id: str, lang: str = "bn", **subs) -> Optional[dict]:
    box = warning_boxes().get(box_id)
    if not box:
        return None
    bn = (lang or "en").startswith("bn")
    title = box.get("title_bn" if bn else "title_en") or ""
    body = box.get("body_bn" if bn else "body_en") or ""
    for k, v in subs.items():
        token = "{" + k + "}"
        title = title.replace(token, str(v))
        body = body.replace(token, str(v))
    return {
        "id": box_id,
        "level": box.get("level"),
        "title": title,
        "body": body,
    }


def _norm(name: str) -> str:
    return (
        (name or "")
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )


def find_treatment(class_name: str = "", kb_key: str = "") -> Optional[dict]:
    if class_name:
        try:
            from agroscan.label_map import merge_class_name

            class_name = merge_class_name(class_name)
        except Exception:
            pass
        hit = treatments_by_class().get(class_name)
        if hit:
            return hit
        want = _norm(class_name)
        for k, v in treatments_by_class().items():
            if _norm(k) == want:
                return v
        # last resort: same crop + overlapping condition token
        if "___" in class_name:
            crop, cond = class_name.split("___", 1)
            crop_n, cond_n = _norm(crop), _norm(cond)
            for k, v in treatments_by_class().items():
                if "___" not in k:
                    continue
                pc, pd = k.split("___", 1)
                if _norm(pc) == crop_n and (cond_n in _norm(pd) or _norm(pd) in cond_n):
                    return v
    if kb_key:
        rows = treatments_by_kb().get(kb_key) or []
        if not rows:
            return None
        # Prefer a Bangladesh-relevant / potato-tomato etc. row; still crop-agnostic kb_key.
        for row in rows:
            if (row.get("bangladesh_relevance") or "") in ("high", "common", "important"):
                return row
        return rows[0]
    return None


def find_crop(name: str) -> Optional[dict]:
    if not name:
        return None
    needle = name.strip().lower()
    for row in crops():
        en = str(row.get("crop_en") or "").lower()
        bn = str(row.get("crop_bn") or "").lower()
        if needle == en or needle == bn:
            return row
        if needle in en or en in needle:
            return row
    return None
