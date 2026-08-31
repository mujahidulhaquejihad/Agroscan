"""Bangladesh crop catalog + simple farm planner (no LLM required).

Uses:
  - Datasets/llm/flora_raw.txt (300 crop directory)
  - Datasets/tabular/crops/final_crops_data.csv (soil/moisture/humidity/temp → crop)
  - Bangladesh seasons (Rabi / Kharif-1 / Kharif-2)
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from . import config

FLORA_TXT = config.FLORA_TXT
CROPS_CSV = config.CROPS_CSV


# month 1-12 → season key
def season_for_month(month: int) -> str:
    if month in (11, 12, 1, 2):
        return "rabi"
    if month in (3, 4, 5, 6):
        return "kharif1"
    return "kharif2"


SEASON_META = {
    "rabi": {
        "en": "Rabi (winter)",
        "bn": "রবি (শীত)",
        "months": [11, 12, 1, 2],
        "default_crops": [
            "Wheat", "Potato", "Mustard", "Lentil (Masoor)", "Tomato",
            "Cabbage (Badhakopi)", "Cauliflower (Fulkopi)", "Onion", "Garlic",
            "Chickpea (Chhola)",
        ],
    },
    "kharif1": {
        "en": "Kharif-1 (pre-monsoon)",
        "bn": "খরিফ-১ (প্রাক-বর্ষা)",
        "months": [3, 4, 5, 6],
        "default_crops": [
            "Rice (Paddy)", "Jute", "Maize (Corn)", "Okra (Lady's finger/Dherosh)",
            "Yardlong bean (Borboti)", "Cucumber (Shosha)", "Eggplant (Brinjal/Begun)",
            "Green Chili", "Sweet gourd (Misti Kumra)",
        ],
    },
    "kharif2": {
        "en": "Kharif-2 (monsoon)",
        "bn": "খরিফ-২ (বর্ষা)",
        "months": [7, 8, 9, 10],
        "default_crops": [
            "Rice (Paddy)", "Taro (Arum/Kachu)", "Water spinach (Kolmi shak)",
            "Bottle gourd (Lau)", "Pointed gourd (Potol)", "Ginger (Ada)",
            "Turmeric (Holud)", "Banana", "Betel leaf (Paan)",
        ],
    },
}

# Simple multicrop companions (Bangladesh-relevant pairs)
MULTICROP = [
    {"main": "Wheat", "with": ["Mustard", "Lentil (Masoor)", "Chickpea (Chhola)"], "note_en": "Rabi relay / intercrop common in BD.", "note_bn": "রবি মৌসুমে সাধারণ মিশ্র/রিলে চাষ।"},
    {"main": "Rice (Paddy)", "with": ["Fish (rice-fish)", "Duck"], "note_en": "Rice–fish where water is managed.", "note_bn": "পানি নিয়ন্ত্রিত এলাকায় ধান-মাছ চাষ।"},
    {"main": "Maize (Corn)", "with": ["Mung bean (Moong)", "Cowpea (Felon)"], "note_en": "Legumes add nitrogen between maize rows.", "note_bn": "ভুট্টার সারিতে ডাল ফসল নাইট্রোজেন যোগায়।"},
    {"main": "Potato", "with": ["Maize (Corn)", "Mustard"], "note_en": "Follow potato with maize/mustard in rotation.", "note_bn": "আলুর পর ভুট্টা/সরিষা রোটেশনে ভালো।"},
    {"main": "Tomato", "with": ["Coriander leaves (Dhania pata)", "Onion"], "note_en": "Border herbs; avoid potato nearby (shared diseases).", "note_bn": "সীমানায় মসলা; কাছে আলু এড়ান (একই রোগ)।"},
    {"main": "Mustard", "with": ["Wheat", "Lentil (Masoor)"], "note_en": "Classic rabi mix.", "note_bn": "ক্লাসিক রবি মিশ্রচাষ।"},
]


@lru_cache(maxsize=1)
def load_flora_crops() -> List[Dict[str, str]]:
    if not FLORA_TXT.exists():
        return []
    text = FLORA_TXT.read_text(encoding="utf-8", errors="replace")
    crops: List[Dict[str, str]] = []
    category = "Other"
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("FLORA"):
            continue
        if re.match(r"^[A-Za-z].*[a-z]$", line) and not re.search(r"\d+\.", line):
            # category headers like "Grains & Cereals"
            if not re.search(r"\d+\.", line):
                category = line
                continue
        for m in re.finditer(r"(\d+)\.\s*([^0-9]+?)(?=(?:\d+\.)|$)", line):
            name = m.group(2).strip(" ,;")
            if name:
                crops.append({"id": m.group(1), "name": name, "category": category})
    return crops


@lru_cache(maxsize=1)
def load_csv_crop_rows() -> List[Dict[str, float | str]]:
    if not CROPS_CSV.exists():
        return []
    rows: List[Dict[str, float | str]] = []
    with CROPS_CSV.open(encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                rows.append(
                    {
                        "soil": float(r["Soil"]),
                        "soil_moisture": float(r["Soil_Moisture"]),
                        "humidity": float(r["Humidity"]),
                        "temperature": float(r["Temperature"]),
                        "crop": str(r["Crop Name"]).strip(),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def _land_note(land_size: float, unit: str, lang: str) -> str:
    # Normalize rough area in decimals (1 decimal ≈ 40 m²; 1 bigha ≈ 33 decimal in many BD areas — varies)
    unit = (unit or "decimal").lower()
    if unit in ("bigha", "বিঘা"):
        decimals = land_size * 33.0
    elif unit in ("acre", "একর"):
        decimals = land_size * 100.0
    else:
        decimals = land_size
    if lang == "bn":
        if decimals < 5:
            return "ছোট জমি — সবজি/মসলা বা আলু দিয়ে শুরু করুন; ঝুঁকি কম রাখুন।"
        if decimals < 33:
            return "মাঝারি জমি — একটি প্রধান ফসল + একটি মিশ্র ফসল ভালো।"
        return "বড় জমি — প্রধান ফসল + রোটেশন/মাল্টিক্রপ পরিকল্পনা করুন।"
    if decimals < 5:
        return "Small plot — favour vegetables/spices or potato; keep risk low."
    if decimals < 33:
        return "Medium plot — one main crop plus one companion/multicrop works well."
    return "Larger area — plan a main crop with rotation / multicrop blocks."


def recommend_crops(
    *,
    district: str = "",
    land_size: float = 10.0,
    land_unit: str = "decimal",
    season: Optional[str] = None,
    month: Optional[int] = None,
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    soil_moisture: Optional[float] = None,
    lang: str = "bn",
) -> Dict[str, Any]:
    """Rule + CSV nearest-neighbour style crop suggestions."""
    if not season:
        from datetime import datetime

        season = season_for_month(month or datetime.now().month)
    season = season.lower().replace("-", "").replace("_", "")
    if season in ("kharif-1", "kharif_1"):
        season = "kharif1"
    if season in ("kharif-2", "kharif_2"):
        season = "kharif2"
    if season not in SEASON_META:
        season = "rabi"

    meta = SEASON_META[season]
    bn = (lang or "en").startswith("bn")

    pack_recs: List[Dict[str, Any]] = []
    try:
        from agrovet.bd_data import crops as pack_crops

        district_l = (district or "").strip().lower()
        for row in pack_crops():
            seasons = [str(s).lower().replace("-", "").replace("_", "") for s in (row.get("seasons") or [])]
            if seasons and season not in seasons:
                continue
            unsuitable = [str(d).lower() for d in (row.get("unsuitable_districts") or [])]
            if district_l and any(district_l in d or d in district_l for d in unsuitable):
                continue
            suitable = [str(d).lower() for d in (row.get("suitable_districts") or [])]
            district_boost = 0
            if district_l and any(district_l in d or d in district_l for d in suitable):
                district_boost = 1000
            profit_mo = row.get("profit_per_decimal_per_month_typical")
            try:
                profit_mo = float(profit_mo or 0)
            except (TypeError, ValueError):
                profit_mo = 0.0
            shop = []
            for item in row.get("shop_products_needed") or []:
                if isinstance(item, dict):
                    shop.append(
                        {
                            "sku": item.get("sku"),
                            "name": item.get("catalogue_name_en") or item.get("name_en") or item.get("name_bn"),
                            "type": item.get("type"),
                            "qty_per_decimal": item.get("qty_per_decimal"),
                        }
                    )
            pack_recs.append(
                {
                    "crop": row.get("crop_bn") if bn else row.get("crop_en"),
                    "crop_en": row.get("crop_en"),
                    "crop_bn": row.get("crop_bn"),
                    "reason": "profit_pack",
                    "source": "crop_profitability",
                    "profit_typical_per_decimal": row.get("expected_profit_bdt_per_decimal_typical"),
                    "profit_min_per_decimal": row.get("expected_profit_bdt_per_decimal_min"),
                    "profit_max_per_decimal": row.get("expected_profit_bdt_per_decimal_max"),
                    "profit_per_month": profit_mo,
                    "duration_days": row.get("duration_days"),
                    "varieties": row.get("recommended_varieties_bd") or [],
                    "risks": row.get("risk_factors_bn") if bn else row.get("risk_factors_en"),
                    "shop_products_needed": shop,
                    "water_need": row.get("water_need"),
                    "_sort": district_boost + profit_mo,
                }
            )
        pack_recs.sort(key=lambda x: x.get("_sort") or 0, reverse=True)
    except Exception:
        pack_recs = []

    season_crops = list(meta["default_crops"])

    # Optional CSV ranking by climate similarity
    csv_hits: List[Dict[str, Any]] = []
    rows = load_csv_crop_rows()
    if rows and temperature is not None:
        scored = []
        for r in rows:
            dist = abs(float(r["temperature"]) - float(temperature))
            if humidity is not None:
                dist += 0.05 * abs(float(r["humidity"]) - float(humidity))
            if soil_moisture is not None:
                dist += 0.05 * abs(float(r["soil_moisture"]) - float(soil_moisture))
            scored.append((dist, r))
        scored.sort(key=lambda x: x[0])
        seen = set()
        for dist, r in scored[:80]:
            name = str(r["crop"])
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            csv_hits.append({"crop": name, "score": round(1.0 / (1.0 + dist), 3)})
            if len(csv_hits) >= 8:
                break

    # Merge: Bangladesh profitability pack first, then season defaults, then csv
    ranked: List[Dict[str, Any]] = []
    seen = set()
    for r in pack_recs:
        key = str(r.get("crop_en") or r.get("crop") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        ranked.append({k: v for k, v in r.items() if k != "_sort"})
        if len(ranked) >= 12:
            break
    if len(ranked) < 8:
        for c in season_crops:
            if c.lower() in seen:
                continue
            seen.add(c.lower())
            ranked.append({"crop": c, "reason": "season_fit", "source": "season_calendar"})
    for h in csv_hits:
        if all(h["crop"].lower() not in x.get("crop", "").lower() and h["crop"].lower() not in str(x.get("crop_en") or "").lower() for x in ranked):
            ranked.append(
                {
                    "crop": h["crop"],
                    "reason": "climate_match",
                    "source": "crop_csv",
                    "score": h["score"],
                }
            )

    multi = []
    for m in MULTICROP:
        if any(m["main"].lower() in r["crop"].lower() or r["crop"].lower() in m["main"].lower() for r in ranked[:6]):
            multi.append(
                {
                    "main": m["main"],
                    "with": m["with"],
                    "note": m["note_bn"] if lang == "bn" else m["note_en"],
                }
            )

    return {
        "district": district or None,
        "season": season,
        "season_label": meta["bn"] if lang == "bn" else meta["en"],
        "land_note": _land_note(land_size, land_unit, lang),
        "recommendations": ranked[:12],
        "multicrop_options": multi,
        "flora_count": len(load_flora_crops()),
        "disclaimer_bn": "এটি সাধারণ পরামর্শ। স্থানীয় মাটি পরীক্ষা ও উপজেলা কৃষি কর্মকর্তা/১৬১২৩ নিশ্চিত করুন। খারাপ বছরে প্রায় প্রতিটি ফসলেই লোকসান হতে পারে।",
        "disclaimer_en": "General guidance only. Confirm with local soil tests and upazila agriculture officer / 16123. Almost every crop can lose money in a bad year.",
    }


def cultivation_outline(crop_name: str, lang: str = "bn") -> Dict[str, Any]:
    """Per-crop outline from the Bangladesh pack when available."""
    name = crop_name.strip()
    bn = (lang or "en").startswith("bn")
    try:
        from agrovet.bd_data import find_crop

        row = find_crop(name)
    except Exception:
        row = None
    if row:
        fert = row.get("fertilizer_plan_bn" if bn else "fertilizer_plan_en") or row.get("fertilizer_plan_en") or []
        fert_lines = []
        for f in fert:
            if isinstance(f, dict):
                fert_lines.append(f"{f.get('stage', '')}: {f.get('product', '')} — {f.get('dose_per_decimal', '')}")
            else:
                fert_lines.append(str(f))
        shop = row.get("shop_products_needed") or []
        if bn:
            steps = [
                {"title": "জাত ও বীজ", "detail": "সুপারিশকৃত জাত: " + ", ".join(row.get("recommended_varieties_bd") or []) + "। বীজ: " + str(row.get("seed_required_per_decimal") or "")},
                {"title": "সার পরিকল্পনা (প্রতি শতাংশ)", "detail": " । ".join(fert_lines) or "স্থানীয় সুপারিশমতো NPK দিন।"},
                {"title": "সময় ও পানি", "detail": f"সময়কাল প্রায় {row.get('duration_days')} দিন। পানির চাহিদা: {row.get('water_need')}।"},
                {"title": "ঝুঁকি", "detail": " । ".join(row.get("risk_factors_bn") or [])},
                {"title": "লাভের হিসাব (প্রতি শতাংশ)", "detail": f"সাধারণ বছর: {row.get('expected_profit_bdt_per_decimal_typical')} টাকা। খারাপ বছর: {row.get('expected_profit_bdt_per_decimal_min')} টাকা। ভালো বছর: {row.get('expected_profit_bdt_per_decimal_max')} টাকা। মাসিক: {row.get('profit_per_decimal_per_month_typical')} টাকা।"},
                {"title": "রোগ নজরদারি", "detail": "পাতায় দাগ দেখলে AgroScan দিয়ে স্ক্যান করুন।"},
            ]
            helpline = "বিস্তারিত মাত্রার জন্য ১৬১২৩ বা উপজেলা কৃষি অফিস। দাম ডিলার নিশ্চিত করবেন।"
        else:
            steps = [
                {"title": "Variety & seed", "detail": "Recommended: " + ", ".join(row.get("recommended_varieties_bd") or []) + ". Seed: " + str(row.get("seed_required_per_decimal") or "")},
                {"title": "Fertiliser (per decimal)", "detail": " | ".join(fert_lines) or "Follow local NPK guidance."},
                {"title": "Duration & water", "detail": f"About {row.get('duration_days')} days. Water need: {row.get('water_need')}."},
                {"title": "Risks", "detail": " | ".join(row.get("risk_factors_en") or [])},
                {"title": "Profit per decimal", "detail": f"Typical: {row.get('expected_profit_bdt_per_decimal_typical')} BDT. Bad year: {row.get('expected_profit_bdt_per_decimal_min')}. Good year: {row.get('expected_profit_bdt_per_decimal_max')}. Per month: {row.get('profit_per_decimal_per_month_typical')} BDT."},
                {"title": "Watch for disease", "detail": "Scan spotted leaves with AgroScan."},
            ]
            helpline = "Call 16123 or your upazila agriculture office. Dealer must confirm prices."
        return {
            "crop": row.get("crop_bn") if bn else row.get("crop_en"),
            "lang": "bn" if bn else "en",
            "steps": steps,
            "helpline": helpline,
            "shop_products_needed": shop,
            "from_pack": True,
        }

    if lang == "bn":
        steps = [
            {"title": "জমি ও মৌসুম নির্বাচন", "detail": f"{name} আপনার এলাকার মৌসুম ও মাটির সাথে মিলিয়ে নিন। জলাবদ্ধ/খরা ঝুঁকি দেখুন।"},
            {"title": "বীজ/চারা সংগ্রহ", "detail": "BADC/নির্ভরযোগ্য ডিলার থেকে সার্টিফাইড বীজ বা সুস্থ চারা নিন।"},
            {"title": "জমি তৈরি", "detail": "চাষ দিয়ে মাটি নরম করুন, আগাছা পরিষ্কার করুন, প্রয়োজনে জৈব সার মেশান।"},
            {"title": "রোপণ ও সার", "detail": "সঠিক দূরত্বে রোপণ করুন। স্থানীয় সুপারিশমতো ইউরিয়া/টিএসপি/এমওপি ভাগ করে দিন।"},
            {"title": "সেচ ও পরিচর্যা", "detail": "গোড়ায় সেচ দিন; পাতা অপ্রয়োজনে ভেজাতে না। আগাছা ও পোকা নজর রাখুন।"},
            {"title": "রোগ নজরদারি", "detail": "সপ্তাহে পাতা দেখুন। দাগ দেখলে AgroScan দিয়ে স্ক্যান করুন এবং পরামর্শমতো ব্যবস্থা নিন।"},
            {"title": "ফসল সংগ্রহ", "detail": "পরিপক্কতা দেখে তুলুন; সংরক্ষণ/বাজারজাত আগে শুকিয়ে/বাছাই করুন।"},
        ]
        return {"crop": name, "lang": "bn", "steps": steps, "helpline": "বিস্তারিত মাত্রার জন্য ১৬১২৩ বা উপজেলা কৃষি অফিস।"}
    steps = [
        {"title": "Choose land & season", "detail": f"Match {name} to your local season and soil; check flood/drought risk."},
        {"title": "Get quality seed/seedlings", "detail": "Use certified seed or healthy seedlings from a trusted source (e.g. BADC dealers)."},
        {"title": "Prepare the land", "detail": "Till, remove weeds, and add organic matter if soil is poor."},
        {"title": "Plant & fertilise", "detail": "Plant at recommended spacing. Split NPK fertiliser as locally advised."},
        {"title": "Irrigate & care", "detail": "Water at the base; avoid unnecessary leaf wetness. Scout for weeds and pests."},
        {"title": "Watch for disease", "detail": "Check leaves weekly. If spots appear, scan with AgroScan and follow next steps."},
        {"title": "Harvest", "detail": "Harvest at maturity; dry/grade before storage or market."},
    ]
    return {"crop": name, "lang": "en", "steps": steps, "helpline": "Call 16123 or your upazila agriculture office for local rates/doses."}
