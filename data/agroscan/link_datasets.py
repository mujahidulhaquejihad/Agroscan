#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgroScan — cross-dataset linking pass.

Turns the human-written product NAME references in disease_treatments.json and
crop_profitability.json into resolved SKU links against products.json and
equipment.json, so the app can go diagnosis -> recommended product -> cart
without any string matching at runtime.

Also:
  * adds explicit cures_disease / targets_vector flags to chemical treatments on
    incurable (viral and bacterial-wilt) classes, so the UI cannot accidentally
    present a vector-control spray as a cure;
  * emits keys_reference.json documenting every controlled vocabulary in the
    dataset.

Idempotent: safe to re-run.
"""
import json, re, unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher

D = "/root/agroscan/data/"


def load(n):
    return json.load(open(D + n, encoding="utf-8"))


def save(n, o):
    json.dump(o, open(D + n, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


dis = load("disease_treatments.json")
crop = load("crop_profitability.json")
prod = load("products.json")
equip = load("equipment.json")

CATALOGUE = [{"sku": p["sku"], "name": p["name_en"], "cat": p["category"],
              "sub": p.get("subcategory"), "ai": p.get("active_ingredient"),
              "brands": p.get("alternative_brands_bd") or ([p["brand"]] if p.get("brand") else []),
              "pack": p.get("pack_size")} for p in prod]
CATALOGUE += [{"sku": e["sku"], "name": e["name_en"], "cat": e["category"],
               "sub": e.get("subcategory"), "ai": None,
               "brands": [e["brand"]] if e.get("brand") else [],
               "pack": None} for e in equip]

STOP = {"the", "for", "and", "with", "per", "of", "a"}


def toks(s):
    s = unicodedata.normalize("NFKD", s).lower()
    s = re.sub(r"\(.*?\)", " ", s)          # drop parenthetical asides
    s = re.sub(r"[^a-z0-9%. ]", " ", s)
    return [t for t in s.split() if t and t not in STOP]


def key(s):
    return " ".join(toks(s))


CAT_KEYS = [(c, key(c["name"])) for c in CATALOGUE]


def resolve(ref):
    """Return (record, score, method) for the best catalogue match, or None."""
    k = key(ref)
    kt = set(toks(ref))
    best, best_score, method = None, 0.0, ""
    for c, ck in CAT_KEYS:
        ct = set(toks(c["name"]))
        if not ct:
            continue
        # token overlap weighted by how much of the REFERENCE is covered
        cover = len(kt & ct) / max(len(kt), 1)
        seq = SequenceMatcher(None, k, ck).ratio()
        score = 0.65 * cover + 0.35 * seq
        # a shared active ingredient is strong evidence
        if c["ai"] and set(toks(c["ai"])) & kt:
            score += 0.15
        # so is an exact brand-name hit: farmers and agronomists write "Nativo 75 WG"
        # where the catalogue is keyed on the active ingredient
        for b in c.get("brands") or []:
            bt = set(toks(b))
            if bt and bt <= kt:
                score += 0.45
                break
        if c.get("pack") and key(c["pack"]) and set(toks(c["pack"])) <= kt:
            score += 0.10
        if score > best_score:
            best, best_score, method = c, score, "token+seq"
    if best_score >= 0.55:
        conf = "high" if best_score >= 0.80 else "medium" if best_score >= 0.66 else "low"
        return best, round(best_score, 3), conf
    return None, round(best_score, 3), "none"


# ------------------------------------------------ 1. link disease -> SKUs
unresolved = Counter()
link_conf = Counter()
for r in dis:
    links = []
    for ref in r.get("related_shop_products", []):
        m, score, conf = resolve(ref)
        if m:
            links.append({"ref_text": ref, "sku": m["sku"], "name_en": m["name"],
                          "category": m["cat"], "match_score": score,
                          "match_confidence": conf})
            link_conf[conf] += 1
        else:
            links.append({"ref_text": ref, "sku": None, "name_en": None,
                          "category": None, "match_score": score,
                          "match_confidence": "unresolved"})
            unresolved[ref] += 1
            link_conf["unresolved"] += 1
    r["related_shop_skus"] = links

# ------------------------------------------------ 2. link crops -> SKUs
crop_unres = Counter()
for r in crop:
    for sp in r.get("shop_products_needed", []):
        m, score, conf = resolve(sp["name_en"])
        if m:
            sp["sku"] = m["sku"]
            sp["catalogue_name_en"] = m["name"]
            sp["match_score"] = score
            sp["match_confidence"] = conf
        else:
            sp["sku"] = None
            sp["catalogue_name_en"] = None
            sp["match_score"] = score
            sp["match_confidence"] = "unresolved"
            crop_unres[sp["name_en"]] += 1

# ------------------------- 3. explicit cure flags on incurable disease classes
INCURABLE = {
    "tylcv": "whitefly (Bemisia tabaci)",
    "tungro": "green leafhopper (Nephotettix spp.)",
    "citrus_greening": "Asian citrus psyllid (Diaphorina citri)",
    "chilli_leaf_curl": "whitefly (Bemisia tabaci) — for the viral component only",
    "tomato_mosaic_virus": None,
    "bacterial_wilt": None,
}
flagged = 0
for r in dis:
    kb = r["kb_key"]
    incurable = kb in INCURABLE
    r["is_curable_with_chemicals"] = not incurable
    if incurable:
        r["no_cure_notice_en"] = (
            "There is no chemical cure for this condition. Plants already affected will not "
            "recover. Any product recommended below protects the plants that are still healthy "
            "or slows the spread — it does not cure an infected plant.")
        r["no_cure_notice_bn"] = (
            "এই সমস্যার কোনো ওষুধ নেই। যেসব গাছ আক্রান্ত হয়ে গেছে সেগুলো আর ভালো হবে না। "
            "নিচে যে ওষুধের কথা বলা হয়েছে তা কেবল সুস্থ গাছগুলোকে রক্ষা করে বা রোগ ছড়ানো ধীর "
            "করে — আক্রান্ত গাছ সারায় না।")
    for ct in r.get("chemical_treatments", []):
        if incurable:
            ct["cures_disease"] = False
            vec = INCURABLE[kb]
            ct["targets_vector"] = vec
            ct["purpose_en"] = (f"Controls the {vec} that spreads the disease, protecting plants "
                                f"that are still healthy. It does NOT cure infected plants."
                                if vec else
                                "Suppresses spread only. It does NOT cure infected plants.")
            ct["purpose_bn"] = ("রোগ ছড়ানো পোকা দমন করে, ফলে যেসব গাছ এখনো সুস্থ সেগুলো বাঁচে। "
                                "আক্রান্ত গাছ এতে সারে না।"
                                if vec else
                                "শুধু ছড়ানো কমায়। আক্রান্ত গাছ এতে সারে না।")
            flagged += 1
        else:
            ct.setdefault("cures_disease", True)
            ct.setdefault("targets_vector", None)

# --------------------------------------------- 4. controlled vocabularies
kb_keys = sorted({r["kb_key"] for r in dis})
prod_keys = sorted({k for p in prod for k in p.get("disease_keys", [])})
pest_only = sorted(set(prod_keys) - set(kb_keys))

keys_ref = {
    "meta": {
        "title": "AgroScan controlled vocabularies and join keys",
        "generated": "2026-08-20",
        "purpose": "Single reference for every key the datasets join on. Read this before writing import code.",
    },
    "join_map": {
        "disease_treatments.class_name": "The AI model's output label. Primary key of Section A. Matches the PlantVillage-style Crop___Condition format.",
        "disease_treatments.kb_key": "Condition slug, NOT unique — deliberately shared across crops where the pathogen and management are the same (for example late_blight covers both Potato___Late_blight and Tomato___Late_blight). Join products to diseases on this.",
        "products.disease_keys[]": "List of kb_key values (and pest keys, see pest_keys below) this product treats.",
        "disease_treatments.related_shop_skus[].sku": "Resolved link into products.sku or equipment.sku. Generated by link_datasets.py.",
        "crop_profitability.shop_products_needed[].sku": "Resolved link into products.sku or equipment.sku.",
        "suppliers.district / suppliers.upazila": "Join to upazilas.district_en / upazilas.upazila_en.",
        "upazilas.upazila_id": "Stable id from the source geocode dataset; safe to use as a foreign key.",
    },
    "kb_keys_in_section_a": kb_keys,
    "pest_keys": {
        "note": "These appear in products.disease_keys but have no Section A disease card, because they are arthropod pests or vertebrate pests rather than conditions the leaf-image model classifies. They exist so the shop can be browsed by problem. Do not treat their absence from Section A as a data error.",
        "keys": pest_only,
    },
    "enums": {
        "source_type": ["official", "academic", "label", "field_guide", "inferred"],
        "confidence": ["high", "medium", "low"],
        "seasons": {"rabi": "November-March", "kharif1": "March-June", "kharif2": "June-October"},
        "severity": ["none", "low", "medium", "high"],
        "treatment_type": ["preventive", "curative", "both"],
        "safety_class": ["low", "moderate", "high"],
        "bangladesh_relevance": {
            "bd_relevant": "field absent — the crop is a mainstream Bangladeshi crop",
            "widely_grown": "grown across the country",
            "grown_commercially_small_scale": "real but small commercial area",
            "grown_regionally": "concentrated in specific districts",
            "niche_commercial": "small niche commercial crop",
            "not_grown_commercially": "not a commercial crop here; treat a prediction as probable misclassification",
            "not_grown": "not grown at all; suppress or hard-warn on this class",
        },
        "product_category": sorted({p["category"] for p in prod}),
        "product_subcategory": sorted({p["subcategory"] for p in prod}),
        "equipment_subcategory": sorted({e["subcategory"] for e in equip}),
        "supplier_type": sorted({s["type"] for s in load("suppliers.json")}),
    },
    "units": {
        "land": "1 decimal = 1/100 acre = 40.47 m2; 1 bigha = 33 decimal; 1 hectare = 247.1 decimal",
        "money": "All prices in BDT. price_bdt_min/max are RANGES, never fixed prices.",
        "dose": "Doses are per litre of spray water unless the field name says per decimal or per hectare.",
        "phi_days": "Integer days between the last application and harvest.",
    },
    "app_logic_flags": {
        "is_curable_with_chemicals": "false on viral classes and bacterial wilt. When false, the UI must show no_cure_notice before any product.",
        "chemical_treatments[].cures_disease": "false where the product only protects healthy plants or slows spread.",
        "chemical_treatments[].targets_vector": "names the insect vector when the spray targets the vector rather than the pathogen.",
        "highly_hazardous_flag": "true when the active ingredient appears on Bangladesh's highly-hazardous-pesticide list. Show the amber caution chip.",
        "subsidy_eligible": "equipment normally covered by the government machinery subsidy; tell the farmer to ask DAE before paying full price.",
    },
}

save("disease_treatments.json", dis)
save("crop_profitability.json", crop)
save("keys_reference.json", keys_ref)

print("LINKING PASS")
print(f"  disease product references resolved: {dict(link_conf)}")
print(f"  distinct unresolved disease refs: {len(unresolved)}")
for r, c in unresolved.most_common(20):
    print(f"    - {r} (x{c})")
print(f"  distinct unresolved crop refs: {len(crop_unres)}")
for r, c in crop_unres.most_common(20):
    print(f"    - {r} (x{c})")
print(f"  chemical entries flagged as non-curative: {flagged}")
print(f"  kb_keys: {len(kb_keys)}   pest-only keys: {len(pest_only)} -> {pest_only}")
