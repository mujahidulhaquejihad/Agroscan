"""Build a strong agriculture Q&A JSONL mix for AgroScan LoRA fine-tuning.

Sources (after `python -m llm.download_datasets`):
  - AgroScan disease guides (EN/BN) + farm planner rules
  - KrishokChat Bengali agri QA (downloaded)
  - English agri QA (if downloaded)
  - Crop recommendation CSVs → climate/soil → crop Q&A

Run:
  python -m llm.download_datasets
  python -m llm.build_qa_dataset

Outputs:
  Datasets/llm/train_qa.jsonl
  Datasets/llm/eval_qa.jsonl
  Datasets/llm/dataset_stats.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "Datasets" / "llm"
TRAIN = OUT_DIR / "train_qa.jsonl"
EVAL = OUT_DIR / "eval_qa.jsonl"
STATS = OUT_DIR / "dataset_stats.json"
KRISHOK = OUT_DIR / "raw" / "huggingface" / "krishokchat" / "qa.jsonl"
EN_QA = OUT_DIR / "raw" / "huggingface" / "english_agri_qa" / "qa.jsonl"
CROPS_DIR = ROOT / "Datasets" / "tabular" / "crops"


def _norm_key(instruction: str, output: str) -> str:
    s = re.sub(r"\s+", " ", (instruction + "||" + output[:200]).lower()).strip()
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _clean_pair(instruction: str, output: str, source: str) -> dict | None:
    instruction = (instruction or "").strip()
    output = (output or "").strip()
    if len(instruction) < 6 or len(output) < 12:
        return None
    if len(instruction) > 1200:
        instruction = instruction[:1200]
    if len(output) > 2500:
        output = output[:2500].rstrip() + "…"
    # Drop near-empty / garbage
    if output.count("�") > 3:
        return None
    return {
        "instruction": instruction,
        "input": "",
        "output": output,
        "source": source,
    }


def _pairs_from_disease_guides() -> list[dict]:
    from agrovet.disease_guides import DISEASE_GUIDES
    from agrovet.disease_guides_bn import DISEASE_GUIDES_BN
    from agrovet.knowledge import DISEASE_INFO
    from agrovet.knowledge_bn import DISEASE_INFO_BN

    rows: list[dict] = []
    templates_en = [
        "A farmer scanned a leaf and AgroScan detected {title}. Give detailed next steps.",
        "My crop has {title}. What should I do step by step?",
        "Explain {title}: symptoms, treatment, prevention, and when to call 16123.",
        "Is {title} serious? What is the expected outcome after treatment?",
    ]
    templates_bn = [
        "কৃষকের পাতায় {title} ধরা পড়েছে। বিস্তারিত পরবর্তী ধাপ বলুন।",
        "আমার ফসলে {title} হয়েছে। ধাপে ধাপে কী করব?",
        "{title} এর লক্ষণ, চিকিৎসা, প্রতিরোধ এবং কখন ১৬১২৩-এ কল করতে হবে বলুন।",
    ]

    for key, info in DISEASE_INFO.items():
        guide = DISEASE_GUIDES.get(key, {})
        bn_info = DISEASE_INFO_BN.get(key, {})
        bn_guide = DISEASE_GUIDES_BN.get(key, {})
        title = str(info.get("title", key))
        title_bn = str(bn_info.get("title", title))

        steps = guide.get("next_steps") or []
        steps_txt = "\n".join(
            f"{i+1}. {s.get('title','')}: {s.get('detail','')}" for i, s in enumerate(steps)
        )
        steps_bn = bn_guide.get("next_steps") or []
        steps_bn_txt = "\n".join(
            f"{i+1}. {s.get('title','')}: {s.get('detail','')}" for i, s in enumerate(steps_bn)
        )

        out_en = (
            f"{guide.get('description','')}\n\nNext steps:\n{steps_txt}\n\n"
            f"Treatment: {'; '.join(info.get('treatment') or [])}\n"
            f"Prevention: {'; '.join(info.get('prevention') or [])}\n"
            f"When to call helpline: {guide.get('when_to_call_helpline','')}\n"
            f"Expected outcome: {guide.get('expected_outcome','')}\n"
            f"Disclaimer: General guidance only — confirm with DAE / 16123."
        )
        out_bn = (
            f"{bn_guide.get('description','')}\n\nপরবর্তী ধাপ:\n{steps_bn_txt}\n\n"
            f"চিকিৎসা: {'; '.join(bn_info.get('treatment') or [])}\n"
            f"প্রতিরোধ: {'; '.join(bn_info.get('prevention') or [])}\n"
            f"হেল্পলাইন: {bn_guide.get('when_to_call_helpline','')}\n"
            f"ফলাফল: {bn_guide.get('expected_outcome','')}\n"
            f"সতর্কতা: সাধারণ পরামর্শ — উপজেলা কৃষি অফিস/১৬১২৩ দিয়ে নিশ্চিত করুন।"
        )

        for t in templates_en:
            p = _clean_pair(t.format(title=title), out_en, "agroscan_disease_en")
            if p:
                rows.append(p)
        for t in templates_bn:
            p = _clean_pair(t.format(title=title_bn), out_bn, "agroscan_disease_bn")
            if p:
                rows.append(p)

        p = _clean_pair(
            f"What is {title}? Summarise symptoms and treatment.",
            f"Summary: {info.get('summary')}\nSymptoms: {', '.join(info.get('symptoms') or [])}\n"
            f"Treatment: {'; '.join(info.get('treatment') or [])}\n"
            f"Prevention: {'; '.join(info.get('prevention') or [])}",
            "agroscan_disease_en",
        )
        if p:
            rows.append(p)
    return rows


def _pairs_from_farm_plan() -> list[dict]:
    from agrovet.farm_plan import (
        MULTICROP,
        SEASON_META,
        cultivation_outline,
        load_flora_crops,
        recommend_crops,
    )

    rows: list[dict] = []
    districts = [
        "Bogura",
        "Dinajpur",
        "Rangpur",
        "Barisal",
        "Rajshahi",
        "Khulna",
        "Sylhet",
        "Mymensingh",
        "Cumilla",
        "Jessore",
    ]
    sizes = [2, 5, 10, 20, 33, 50]
    units = ["decimal", "bigha"]

    for season, meta in SEASON_META.items():
        for dist in districts:
            for size in sizes:
                for unit in units:
                    plan = recommend_crops(
                        district=dist,
                        land_size=float(size),
                        land_unit=unit,
                        season=season,
                        lang="en",
                    )
                    crops = ", ".join(c["crop"] for c in plan["recommendations"][:8])
                    multi = "; ".join(
                        f"{m['main']} + {', '.join(m['with'])}"
                        for m in plan.get("multicrop_options") or []
                    )
                    out = (
                        f"Season: {meta['en']}. Area: {dist}. Land: {size} {unit}.\n"
                        f"Suggested crops: {crops}.\n"
                        f"Land note: {plan['land_note']}\n"
                        f"Multicrop: {multi or 'See mustard/wheat or maize/legume options where relevant.'}\n"
                        f"Confirm with local soil test and 16123 / upazila agriculture office."
                    )
                    p = _clean_pair(
                        f"I farm in {dist}, Bangladesh during {meta['en']}. "
                        f"My land is {size} {unit}. What should I grow? Include multicrop if possible.",
                        out,
                        "agroscan_farm_en",
                    )
                    if p:
                        rows.append(p)

                    plan_bn = recommend_crops(
                        district=dist,
                        land_size=float(size),
                        land_unit=unit,
                        season=season,
                        lang="bn",
                    )
                    crops_bn = ", ".join(c["crop"] for c in plan_bn["recommendations"][:8])
                    out_bn = (
                        f"মৌসুম: {meta['bn']}। এলাকা: {dist}। জমি: {size} {unit}।\n"
                        f"প্রস্তাবিত ফসল: {crops_bn}।\n"
                        f"নোট: {plan_bn['land_note']}\n"
                        f"উপজেলা কৃষি অফিস/১৬১২৩ দিয়ে নিশ্চিত করুন।"
                    )
                    p = _clean_pair(
                        f"আমি {dist}-এ {meta['bn']} মৌসুমে চাষ করি। জমি {size} {unit}। কী চাষ করব? মাল্টিক্রপ থাকলে বলুন।",
                        out_bn,
                        "agroscan_farm_bn",
                    )
                    if p:
                        rows.append(p)

    for m in MULTICROP:
        p = _clean_pair(
            f"Can I multicrop with {m['main']} in Bangladesh?",
            f"Yes. Common companions: {', '.join(m['with'])}. {m['note_en']}",
            "agroscan_multicrop",
        )
        if p:
            rows.append(p)
        p = _clean_pair(
            f"{m['main']} এর সাথে মাল্টিক্রপ করা যায় কি?",
            f"হ্যাঁ। সাধারণ সঙ্গী: {', '.join(m['with'])}। {m['note_bn']}",
            "agroscan_multicrop",
        )
        if p:
            rows.append(p)

    # Flora cultivation outlines for many crops
    flora = load_flora_crops()
    priority = [
        c["name"]
        for c in flora
        if any(
            k in c["name"].lower()
            for k in (
                "rice",
                "wheat",
                "maize",
                "potato",
                "tomato",
                "mustard",
                "jute",
                "lentil",
                "onion",
                "garlic",
                "eggplant",
                "chili",
                "mango",
                "banana",
                "sugarcane",
                "tea",
                "groundnut",
                "sesame",
                "cabbage",
                "cauliflower",
                "okra",
                "cucumber",
                "ginger",
                "turmeric",
            )
        )
    ]
    # ensure uniqueness preserve order
    seen = set()
    crops_list = []
    for n in priority:
        if n.lower() not in seen:
            seen.add(n.lower())
            crops_list.append(n)
    for crop in crops_list[:40]:
        en = cultivation_outline(crop, "en")
        bn = cultivation_outline(crop, "bn")
        p = _clean_pair(
            f"How do I cultivate {crop} step by step in Bangladesh?",
            "\n".join(f"{i+1}. {s['title']}: {s['detail']}" for i, s in enumerate(en["steps"]))
            + f"\nHelpline: {en.get('helpline','')}",
            "agroscan_cultivate",
        )
        if p:
            rows.append(p)
        p = _clean_pair(
            f"{crop} চাষের ধাপগুলো কী কী?",
            "\n".join(f"{i+1}. {s['title']}: {s['detail']}" for i, s in enumerate(bn["steps"]))
            + f"\nহেল্পলাইন: {bn.get('helpline','')}",
            "agroscan_cultivate",
        )
        if p:
            rows.append(p)
    return rows


def _pairs_from_jsonl(path: Path, source: str, limit: int) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if len(rows) >= limit:
                break
            try:
                ex = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = _clean_pair(
                ex.get("instruction") or ex.get("question") or "",
                ex.get("output") or ex.get("answer") or "",
                source,
            )
            if p:
                rows.append(p)
    return rows


def _pairs_from_crop_csvs(limit: int = 8000) -> list[dict]:
    rows: list[dict] = []
    # final_crops_data.csv: Soil, Soil_Moisture, Humidity, Temperature, Crop Name
    p1 = CROPS_DIR / "final_crops_data.csv"
    if p1.exists():
        with p1.open(encoding="utf-8", errors="replace") as f:
            for i, r in enumerate(csv.DictReader(f)):
                if i >= limit // 2:
                    break
                try:
                    crop = r["Crop Name"].strip()
                    t = float(r["Temperature"])
                    h = float(r["Humidity"])
                    m = float(r["Soil_Moisture"])
                except (KeyError, ValueError):
                    continue
                p = _clean_pair(
                    f"My field temperature is about {t:.1f}°C, humidity {h:.0f}%, "
                    f"soil moisture {m:.0f}. Which crop is suitable?",
                    f"Based on similar climate records, a suitable crop is {crop}. "
                    f"Also check your local season (Rabi/Kharif), soil type, and confirm with 16123.",
                    "crop_csv_bd",
                )
                if p:
                    rows.append(p)
                p = _clean_pair(
                    f"তাপমাত্রা ~{t:.1f}°C, আর্দ্রতা ~{h:.0f}%, মাটির আর্দ্রতা ~{m:.0f}। কোন ফসল ভালো?",
                    f"অনুরূপ জলবায়ু রেকর্ড অনুযায়ী উপযোগী ফসল: {crop}। "
                    f"স্থানীয় মৌসুম ও মাটি দেখে উপজেলা কৃষি অফিস/১৬১২৩ দিয়ে নিশ্চিত করুন।",
                    "crop_csv_bd",
                )
                if p:
                    rows.append(p)

    # Bangladesh_Crop_Dataset-50k.csv
    p2 = CROPS_DIR / "Bangladesh_Crop_Dataset-50k.csv"
    if p2.exists():
        with p2.open(encoding="utf-8", errors="replace") as f:
            for i, r in enumerate(csv.DictReader(f)):
                if i >= limit // 2:
                    break
                label = (r.get("label") or "").strip()
                if not label:
                    continue
                try:
                    t = float(r.get("temperature") or 0)
                    h = float(r.get("humidity") or 0)
                    rain = float(r.get("rainfall") or 0)
                    ph = float(r.get("ph") or 0)
                    soil = r.get("soil") or "local soil"
                except ValueError:
                    continue
                p = _clean_pair(
                    f"Soil={soil}, pH={ph:.1f}, temp={t:.1f}°C, humidity={h:.0f}%, rainfall={rain:.0f}mm. Recommend a crop.",
                    f"Recommended crop label from similar BD records: {label}. "
                    f"Validate against your district season and irrigation before planting.",
                    "crop_csv_50k",
                )
                if p:
                    rows.append(p)

    # classic NPK dataset
    p3 = CROPS_DIR / "crop_recommendation_classic.csv"
    if p3.exists():
        with p3.open(encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, r in enumerate(reader):
                if i >= 3000:
                    break
                # flexible column names
                label = (r.get("label") or r.get("crop") or r.get("Crop") or "").strip()
                if not label:
                    continue
                n = r.get("N") or r.get("n") or "?"
                p_ = r.get("P") or r.get("p") or "?"
                k = r.get("K") or r.get("k") or "?"
                pair = _clean_pair(
                    f"Soil nutrients N={n}, P={p_}, K={k}. Which crop fits?",
                    f"A matching crop from nutrient tables is {label}. Adjust for Bangladesh season and local variety.",
                    "crop_csv_classic",
                )
                if pair:
                    rows.append(pair)
    return rows


def _dedupe(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        k = _norm_key(r["instruction"], r["output"])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    print("Building AgroScan disease + farm pairs…")
    rows = _pairs_from_disease_guides() + _pairs_from_farm_plan()
    print(f"  agroscan core: {len(rows)}")

    print("Loading KrishokChat…")
    k = _pairs_from_jsonl(KRISHOK, "krishokchat", limit=60000)
    print(f"  krishokchat: {len(k)}")
    rows.extend(k)

    print("Loading English agri QA…")
    e = _pairs_from_jsonl(EN_QA, "english_agri", limit=10000)
    print(f"  english: {len(e)}")
    rows.extend(e)

    print("Building crop CSV pairs…")
    c = _pairs_from_crop_csvs(limit=10000)
    print(f"  crop csv: {len(c)}")
    rows.extend(c)

    rows = _dedupe(rows)
    rng.shuffle(rows)

    # Cap very large sets but keep quality mix
    max_total = 75000
    if len(rows) > max_total:
        # Keep all agroscan_* then fill rest
        core = [r for r in rows if str(r.get("source", "")).startswith("agroscan")]
        other = [r for r in rows if not str(r.get("source", "")).startswith("agroscan")]
        need = max(0, max_total - len(core))
        rows = core + other[:need]
        rng.shuffle(rows)

    n_eval = max(200, min(2000, len(rows) // 20))
    eval_rows = rows[:n_eval]
    train_rows = rows[n_eval:]

    def write(path: Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for r in data:
                # training format without extra fields required, keep source for analysis
                f.write(
                    json.dumps(
                        {
                            "instruction": r["instruction"],
                            "input": r.get("input", ""),
                            "output": r["output"],
                            "source": r.get("source", ""),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    write(TRAIN, train_rows)
    write(EVAL, eval_rows)
    counts = Counter(r.get("source", "") for r in train_rows)
    stats = {
        "train": len(train_rows),
        "eval": len(eval_rows),
        "by_source": dict(counts),
    }
    STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(train_rows)} train -> {TRAIN}")
    print(f"Wrote {len(eval_rows)} eval  -> {EVAL}")
    print(f"Stats -> {STATS}")
    print("Sources:", dict(counts))


if __name__ == "__main__":
    main()
