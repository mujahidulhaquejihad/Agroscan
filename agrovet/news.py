"""Farmer news / advisory bulletins for the Notifications tab."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config

NEWS_PATH = config.AGROSCAN_PACK_DIR / "farmer_news.json"


def _load_raw() -> List[dict]:
    if not NEWS_PATH.exists():
        return []
    try:
        data = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _pick(item: dict, lang: str, field: str) -> str:
    bn = (lang or "").startswith("bn")
    if bn:
        return str(item.get(f"{field}_bn") or item.get(f"{field}_en") or item.get(field) or "")
    return str(item.get(f"{field}_en") or item.get(f"{field}_bn") or item.get(field) or "")


def _seasonal_extra(lang: str) -> List[dict]:
    """Month-aware tips generated at request time."""
    m = date.today().month
    bn = (lang or "").startswith("bn")
    tips: List[dict] = []
    if m in (11, 12, 1, 2):
        tips.append(
            {
                "id": f"auto-rabi-{date.today().isoformat()}",
                "date": date.today().isoformat(),
                "priority": "high",
                "category": "season",
                "title": "কুয়াশা মৌসুম সতর্কতা" if bn else "Rabi fog season alert",
                "body": (
                    "আলু/টমেটো জমিতে নাবি ধ্বসা পরীক্ষা করুন। সকালে পাতার নিচের দিক দেখুন।"
                    if bn
                    else "Check potato/tomato fields for late blight. Inspect the underside of leaves in the morning."
                ),
                "link": None,
                "source": "season",
            }
        )
    if m in (6, 7, 8, 9, 10):
        tips.append(
            {
                "id": f"auto-kharif-{date.today().isoformat()}",
                "date": date.today().isoformat(),
                "priority": "normal",
                "category": "season",
                "title": "বর্ষা মৌসুম: ধান ও সবজি নজরদারি" if bn else "Monsoon: scout rice & vegetables",
                "body": (
                    "ব্লাস্ট/BLB ও সবজির পাতার দাগ বাড়তে পারে। সপ্তাহে একবার জমি ঘুরুন।"
                    if bn
                    else "Blast/BLB and vegetable leaf spots can rise. Walk your field once a week."
                ),
                "link": None,
                "source": "season",
            }
        )
    return tips


def list_news(lang: str = "bn", limit: int = 40) -> Dict[str, Any]:
    lang = lang or "bn"
    items: List[dict] = []
    for raw in _load_raw():
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or "").strip()
        if not nid:
            continue
        items.append(
            {
                "id": nid,
                "date": str(raw.get("date") or ""),
                "priority": str(raw.get("priority") or "normal"),
                "category": str(raw.get("category") or "tip"),
                "title": _pick(raw, lang, "title"),
                "body": _pick(raw, lang, "body"),
                "link": raw.get("link"),
                "source": "pack",
            }
        )
    items.extend(_seasonal_extra(lang))

    def sort_key(it: dict):
        pri = 0 if it.get("priority") == "high" else 1
        return (pri, str(it.get("date") or ""), str(it.get("id") or ""))

    items.sort(key=sort_key)
    # Newest dates first within priority — re-sort by date desc then priority
    def sort_key2(it: dict):
        pri = 0 if it.get("priority") == "high" else 1
        return (pri, str(it.get("date") or "0000"), str(it.get("id") or ""))

    items.sort(key=sort_key2, reverse=False)
    # Actually want: high first, then newest date
    items.sort(
        key=lambda it: (
            0 if it.get("priority") == "high" else 1,
            # reverse date: negate by sorting date descending via inverted string compare
            "".join(chr(255 - ord(c)) for c in str(it.get("date") or "")),
        )
    )

    updated = None
    if NEWS_PATH.exists():
        try:
            updated = datetime.utcfromtimestamp(NEWS_PATH.stat().st_mtime).isoformat() + "Z"
        except Exception:
            updated = None

    return {
        "items": items[: max(1, min(limit, 80))],
        "updated_at": updated,
        "count": min(len(items), max(1, min(limit, 80))),
    }
