#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AgroScan dataset validation and cross-reference integrity check."""
import json, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

D = str(Path(__file__).resolve().parent) + "/"
fails, warns = [], []


def fail(m): fails.append(m)
def warn(m): warns.append(m)


def load(name):
    with open(D + name, encoding="utf-8") as f:
        return json.load(f)


print("=" * 78)
print("AGROSCAN DATASET VALIDATION")
print("=" * 78)

# ---------------------------------------------------------------- load all
files = ["products.json", "equipment.json",
         "suppliers.json", "upazilas.json", "crop_profitability.json",
         "regulatory_safety.json", "order_workflow.json"]
data = {}
for f in files:
    try:
        data[f] = load(f)
        n = len(data[f]) if isinstance(data[f], list) else "obj"
        print(f"  OK  {f:32} {n}")
    except Exception as e:
        fail(f"{f} failed to parse: {e}")
        print(f"  FAIL {f}: {e}")

dis = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(D, "diseases").glob("*.json"))]
print(f"  OK  {'diseases/*.json':32} {len(dis)} files")
prod = data["products.json"]
equip = data["equipment.json"]
sup = data["suppliers.json"]
upz = data["upazilas.json"]
crop = data["crop_profitability.json"]
reg = data["regulatory_safety.json"]

# ------------------------------------------------- 1. required metadata
print("\n[1] Required metadata fields on every record")
META = ["source", "source_type", "last_verified", "confidence"]
for label, rows in [("disease", dis), ("products", prod), ("crops", crop)]:
    miss = defaultdict(int)
    for r in rows:
        for m in META:
            if m not in r or r[m] in (None, ""):
                miss[m] += 1
    if miss:
        fail(f"{label}: missing metadata {dict(miss)}")
    print(f"  {label:10} {'OK' if not miss else dict(miss)}")
# equipment/suppliers use the same fields minus a couple
for label, rows, req in [("equipment", equip, ["source", "source_type", "last_verified", "confidence"]),
                         ("suppliers", sup, ["source", "source_type", "last_verified", "confidence"])]:
    miss = defaultdict(int)
    for r in rows:
        for m in req:
            if m not in r or r[m] in (None, ""):
                miss[m] += 1
    if miss:
        fail(f"{label}: missing metadata {dict(miss)}")
    print(f"  {label:10} {'OK' if not miss else dict(miss)}")

VALID_ST = {"official", "academic", "label", "field_guide", "inferred"}
VALID_CONF = {"high", "medium", "low"}
bad_st = Counter()
bad_cf = Counter()
for rows in (dis, prod, equip, sup, crop):
    for r in rows:
        if r.get("source_type") not in VALID_ST:
            bad_st[r.get("source_type")] += 1
        if r.get("confidence") not in VALID_CONF:
            bad_cf[r.get("confidence")] += 1
if bad_st: fail(f"invalid source_type values: {dict(bad_st)}")
if bad_cf: fail(f"invalid confidence values: {dict(bad_cf)}")
print(f"  enum values: {'OK' if not bad_st and not bad_cf else 'FAIL'}")

# --------------------------------------- 2. Quality Rule 9: healthy = no pesticide
print("\n[2] Quality Rule 9 — healthy classes carry NO pesticide recommendation")
bad = [r["class_name"] for r in dis
       if ("healthy" in r["kb_key"].lower() or r.get("disease_en") == "Healthy")
       and r.get("chemical_treatments")]
if bad: fail(f"healthy classes with chemical_treatments: {bad}")
healthy_n = sum(1 for r in dis if "healthy" in r["kb_key"].lower())
print(f"  {healthy_n} healthy classes, {len(bad)} violations -> {'OK' if not bad else 'FAIL'}")

# ----------------------------- 3. viral / incurable classes must have no chem cure
print("\n[3] Viral and incurable classes must not imply a cure")
INCURABLE = {
    "tylcv", "tomato_mosaic_virus", "tungro", "citrus_greening",
    "bacterial_wilt", "chilli_leaf_curl", "panama", "golden_mosaic",
    "papaya_mosaic", "papaya_ringspot", "papaya_curl", "sugarcane_mosaic",
    "sugarcane_yellow", "potato_brown_rot", "potato_blackleg",
}
bad_cure = []
for r in dis:
    inc = r["kb_key"] in INCURABLE
    if r.get("is_curable_with_chemicals") is None:
        fail(f"{r['class_name']}: is_curable_with_chemicals flag missing")
    elif r["is_curable_with_chemicals"] == inc:
        fail(f"{r['class_name']}: is_curable_with_chemicals={r['is_curable_with_chemicals']} "
             f"but kb_key incurable={inc}")
    if inc:
        if not r.get("no_cure_notice_en") or not r.get("no_cure_notice_bn"):
            fail(f"{r['class_name']}: incurable class missing no_cure_notice")
        for ct in r.get("chemical_treatments", []):
            if ct.get("cures_disease") is not False:
                bad_cure.append((r["class_name"], ct.get("product_name_en")))
    if r["kb_key"] == "tomato_mosaic_virus" and r.get("chemical_treatments"):
        fail(f"{r['class_name']} should have zero chemical_treatments")
if bad_cure: fail(f"incurable classes with cures_disease != false: {bad_cure}")
inc_n = sum(1 for r in dis if not r.get("is_curable_with_chemicals", True))
print(f"  {len(INCURABLE)} incurable kb_keys; {inc_n} records flagged is_curable_with_chemicals=false")
print(f"  chemical entries wrongly claiming a cure: {len(bad_cure)}")

# --------------------------------------------- 4. dose / PHI completeness
print("\n[4] Chemical treatment completeness (dose, PHI, interval, registration)")
REQ_CT = ["product_name_en", "product_name_bn", "active_ingredient", "dose_en", "dose_bn",
          "phi_days", "interval_days", "max_applications_per_season",
          "registered_in_bd", "registration_ref", "treatment_type"]
ct_total = 0
ct_miss = defaultdict(int)
for r in dis:
    for ct in r.get("chemical_treatments", []):
        ct_total += 1
        for k in REQ_CT:
            if k not in ct or ct[k] in (None, ""):
                ct_miss[k] += 1
if ct_miss: fail(f"chemical_treatments missing fields: {dict(ct_miss)}")
print(f"  {ct_total} chemical treatment entries, missing: {dict(ct_miss) or 'none'}")

no_phi = [(r["class_name"], ct["product_name_en"]) for r in dis
          for ct in r.get("chemical_treatments", [])
          if not isinstance(ct.get("phi_days"), int)]
if no_phi: fail(f"chemical entries without an integer PHI: {no_phi[:5]}")
print(f"  every chemical entry has an integer PHI: {'OK' if not no_phi else 'FAIL'}")

# ----------------------------------------- 5. Bangla present on farmer-facing text
print("\n[5] Bangla present on farmer-facing fields")
BN = re.compile(r"[ঀ-৿]")
BN_PAIRS = ["summary", "symptoms", "cultural_control", "organic_alternatives",
            "fertilizer_advice", "safety_warning", "legal_note",
            "when_to_call_helpline", "expected_outcome"]
missing_bn = defaultdict(int)
for r in dis:
    for base in BN_PAIRS:
        k = base + "_bn"
        v = r.get(k)
        if v is None:
            missing_bn[k] += 1
            continue
        txt = " ".join(v) if isinstance(v, list) else str(v)
        if txt.strip() and not BN.search(txt):
            missing_bn[k + " (no Bangla chars)"] += 1
    for step in r.get("immediate_actions_bn", []):
        if not BN.search(step.get("title", "") + step.get("detail", "")):
            missing_bn["immediate_actions_bn (no Bangla chars)"] += 1
if missing_bn: fail(f"disease Bangla gaps: {dict(missing_bn)}")
print(f"  disease records: {dict(missing_bn) or 'all Bangla fields present and non-Latin'}")

for label, rows, keys in [("products", prod, ["name_bn", "description_bn", "usage_summary_bn"]),
                          ("equipment", equip, ["name_bn", "specs_bn", "typical_use_bn",
                                                "maintenance_tips_bn"]),
                          ("crops", crop, ["crop_bn"])]:
    gaps = defaultdict(int)
    for r in rows:
        for k in keys:
            v = r.get(k)
            if v is None or (isinstance(v, str) and v.strip() and not BN.search(v)):
                gaps[k] += 1
    if gaps: warn(f"{label} Bangla gaps: {dict(gaps)}")
    print(f"  {label:10} {dict(gaps) or 'OK'}")

# -------------------------------------- 6. cross-reference kb_key <-> disease_keys
print("\n[6] Cross-reference: products.disease_keys -> disease_treatments.kb_key")
kb = {r["kb_key"] for r in dis}
prod_keys = {k for p in prod for k in p.get("disease_keys", [])}
orphan = sorted(prod_keys - kb)
try:
    documented = set(load("keys_reference.json")["pest_keys"]["keys"])
except Exception:
    documented = set()
undocumented = sorted(set(orphan) - documented)
if undocumented:
    warn(f"product disease_keys with no disease card AND not documented as pest keys: {undocumented}")
print(f"  {len(kb)} kb_keys in Section A; {len(prod_keys)} referenced by products")
print(f"  pest-only keys (documented in keys_reference.json): {len(orphan)}")
print(f"  undocumented orphan keys: {undocumented or 'none'}")

GUARD = {r["kb_key"] for r in dis
         if r.get("bangladesh_relevance") in {"not_grown", "not_grown_commercially",
                                              "rare_experimental"}}
NOCHEM = {"tomato_mosaic_virus"}
relevant = {k for k in kb if not k.startswith("healthy")} - GUARD - NOCHEM
covered = sorted(k for k in relevant if k in prod_keys)
uncovered = sorted(k for k in relevant if k not in prod_keys)
print(f"  Bangladesh-relevant treatable kb_keys: {len(relevant)}")
print(f"  with at least one shop product: {len(covered)}")
print(f"  with NO shop product: {uncovered or 'none'}")
print(f"  guard/no-chem kb_keys excluded from this check: {len(GUARD | NOCHEM)}")
if uncovered:
    warn(f"Bangladesh-relevant kb_keys with no linked product: {uncovered}")

# --------------------------- 7. related_shop_products -> catalogue name check
print("\n[7] Cross-reference: disease.related_shop_skus -> catalogue SKUs")
sku_index = {p["sku"]: p["name_en"] for p in prod}
sku_index.update({e["sku"]: e["name_en"] for e in equip})
total_refs = unres = badsku = 0
conf_mix = Counter()
for r in dis:
    if "related_shop_skus" not in r:
        fail(f"{r['class_name']}: related_shop_skus missing — run link_datasets.py")
        continue
    if len(r["related_shop_skus"]) != len(r.get("related_shop_products", [])):
        fail(f"{r['class_name']}: related_shop_skus length does not match related_shop_products")
    for l in r["related_shop_skus"]:
        total_refs += 1
        conf_mix[l["match_confidence"]] += 1
        if l["sku"] is None:
            unres += 1
        elif l["sku"] not in sku_index:
            badsku += 1
print(f"  {total_refs} references; unresolved: {unres}; dangling SKUs: {badsku}")
print(f"  match confidence: {dict(conf_mix)}")
if unres: fail(f"{unres} disease product references did not resolve to a SKU")
if badsku: fail(f"{badsku} related_shop_skus point at a SKU that does not exist")

# ------------------------------------------ 8. crops -> shop products check
print("\n[8] Cross-reference: crop.shop_products_needed -> catalogue SKUs")
crefs = cunres = cbad = 0
for r in crop:
    for sp in r.get("shop_products_needed", []):
        crefs += 1
        if "sku" not in sp:
            fail(f"{r['crop_en']}: shop_products_needed entry not linked — run link_datasets.py")
        elif sp["sku"] is None:
            cunres += 1
        elif sp["sku"] not in sku_index:
            cbad += 1
print(f"  {crefs} references; unresolved: {cunres}; dangling SKUs: {cbad}")
if cunres: fail(f"{cunres} crop product references did not resolve to a SKU")
if cbad: fail(f"{cbad} crop shop_products_needed point at a SKU that does not exist")

# ------------------------------------------------- 9. no fake phone numbers
print("\n[9] No invented phone numbers in suppliers")
PHONE = re.compile(r"(\+?88)?01[3-9]\d{8}")
bad_phone = [(r["name_en"], r.get("phone")) for r in sup if r.get("phone")]
if bad_phone:
    fail(f"supplier records carry phone numbers that must be verified: {bad_phone[:5]}")
print(f"  supplier records: {len(sup)}; with a phone number: {len(bad_phone)}")
print(f"  all verified=false: {'OK' if all(not r.get('verified') for r in sup) else 'FAIL'}")
blob = json.dumps(sup, ensure_ascii=False)
stray = PHONE.findall(blob)
print(f"  stray BD mobile patterns anywhere in the file: {len(stray)}")
if stray: fail(f"stray phone-like strings in suppliers.json: {stray[:5]}")

# ---------------------------------------------- 10. HHP flagging consistency
print("\n[10] Highly hazardous pesticide flagging")
hhp_topic = next(t for t in reg["topics"] if t["topic"] == "banned_restricted_pesticides")
hhp = set()
for k in ("hhp_widely_used", "hhp_moderately_used"):
    hhp |= {n.lower() for n in hhp_topic["banned_or_restricted_reference"][k]}
flagged = {p["active_ingredient"].lower() for p in prod if p.get("highly_hazardous_flag")}
should = set()
for p in prod:
    ai = (p.get("active_ingredient") or "").lower()
    if any(h in ai for h in hhp):
        should.add(ai)
missed = sorted(should - flagged)
print(f"  HHP actives in Section G list: {len(hhp)}")
print(f"  product actives flagged: {sorted(flagged)}")
if missed:
    warn(f"actives matching the HHP list but NOT flagged: {missed}")
print(f"  unflagged matches: {missed or 'none'}")

# --------------------------------------------------- 11. upazila geo sanity
print("\n[11] Upazila geo dataset")
print(f"  records: {len(upz)}  districts: {len({r['district_en'] for r in upz})}"
      f"  divisions: {len({r['division_en'] for r in upz})}")
oob = [r["upazila_en"] for r in upz
       if not (20.5 <= r["lat"] <= 26.7 and 88.0 <= r["lng"] <= 92.7)]
if oob: fail(f"upazilas outside Bangladesh bbox: {oob}")
dupes = [k for k, v in Counter((r["district_en"], r["upazila_en"]) for r in upz).items() if v > 1]
if dupes: fail(f"duplicate district/upazila pairs: {dupes}")
print(f"  outside BD bbox: {len(oob)}   duplicates: {len(dupes)}")
print(f"  confidence: {dict(Counter(r['confidence'] for r in upz))}")
no_bn = [r["upazila_en"] for r in upz if not BN.search(r["upazila_bn"] or "")]
if no_bn: fail(f"upazilas without a Bangla name: {no_bn[:5]}")
print(f"  all have Bangla names: {'OK' if not no_bn else 'FAIL'}")

# -------------------------------------- 12. Phase-1 upazilas present in geo
print("\n[12] Phase-1 upazilas resolvable in the geo dataset")
P1 = [("Dhaka", "Savar"), ("Dhaka", "Dhamrai"), ("Dhaka", "Keraniganj"),
      ("Gazipur", "Kaliakair"), ("Gazipur", "Kapasia"),
      ("Mymensingh", "Trishal"), ("Mymensingh", "Gafargaon"),
      ("Rajshahi", "Paba"), ("Rajshahi", "Tanore"),
      ("Khulna", "Dumuria"), ("Khulna", "Digholia"),
      ("Sylhet", "Golapganj"), ("Sylhet", "Beanibazar"),
      ("Barisal", "Babuganj"), ("Rangpur", "Badargonj")]
idx = {(r["district_en"], r["upazila_en"]): r for r in upz}
miss_p1 = [p for p in P1 if p not in idx]
if miss_p1: fail(f"Phase-1 upazilas not found in upazilas.json: {miss_p1}")
print(f"  {len(P1) - len(miss_p1)}/{len(P1)} found; missing: {miss_p1 or 'none'}")

# -------------------------------------------- 13. crop economics reconcile
print("\n[13] Crop economics arithmetic reconciles")
bad_math = []
for r in crop:
    g_min = round(r["expected_yield_per_decimal_kg_min"] * r["market_price_bdt_per_kg_min"])
    g_max = round(r["expected_yield_per_decimal_kg_max"] * r["market_price_bdt_per_kg_max"])
    if g_min != r["gross_return_bdt_per_decimal_min"]: bad_math.append((r["crop_en"], "gross_min"))
    if g_max != r["gross_return_bdt_per_decimal_max"]: bad_math.append((r["crop_en"], "gross_max"))
    if g_min - r["input_cost_bdt_per_decimal_max"] != r["expected_profit_bdt_per_decimal_min"]:
        bad_math.append((r["crop_en"], "profit_min"))
    if g_max - r["input_cost_bdt_per_decimal_min"] != r["expected_profit_bdt_per_decimal_max"]:
        bad_math.append((r["crop_en"], "profit_max"))
    if r["expected_profit_bdt_per_bigha_typical"] != r["expected_profit_bdt_per_decimal_typical"] * 33:
        bad_math.append((r["crop_en"], "bigha_typical"))
if bad_math: fail(f"crop economics do not reconcile: {bad_math}")
print(f"  {len(crop)} crops checked; arithmetic errors: {len(bad_math)}")
mono = [r["crop_en"] for r in crop
        if not (r["expected_profit_bdt_per_decimal_min"]
                <= r["expected_profit_bdt_per_decimal_typical"]
                <= r["expected_profit_bdt_per_decimal_max"])]
if mono: fail(f"typical profit outside the min-max band: {mono}")
print(f"  typical always inside the min-max band: {'OK' if not mono else 'FAIL'}")

# -------------------------------------- 14. price ranges are ranges, not points
print("\n[14] Prices are ranges, and min <= max everywhere")
bad_rng = []
for label, rows in [("products", prod), ("equipment", equip)]:
    for r in rows:
        lo, hi = r.get("price_bdt_min"), r.get("price_bdt_max")
        if lo is None or hi is None or lo > hi or lo <= 0:
            bad_rng.append((label, r.get("sku"), lo, hi))
if bad_rng: fail(f"bad price ranges: {bad_rng[:5]}")
print(f"  bad price ranges: {len(bad_rng)}")

# ----------------------------------------------- 15. PlantVillage guard classes
print("\n[15] Bangladesh-relevance guard classes")
guards = [r for r in dis if r.get("bangladesh_relevance") in
          {"not_grown", "not_grown_commercially", "rare_experimental"}]
bad_guard = [r["class_name"] for r in guards if r.get("chemical_treatments")]
if bad_guard: fail(f"guard classes recommending chemicals: {bad_guard}")
print(f"  {len(guards)} guard classes; recommending chemicals: {len(bad_guard)}")
print(f"  relevance breakdown: {dict(Counter(r.get('bangladesh_relevance', 'bd_relevant') for r in dis))}")

# ------------------------------------------------------ 16. season / month sanity
print("\n[16] Season and month values")
VALID_SEASON = {"rabi", "kharif1", "kharif2"}
bad_season = [(r["class_name"], s) for r in dis for s in r.get("seasons_relevant", [])
              if s not in VALID_SEASON]
bad_month = [(r["class_name"], m) for r in dis for m in r.get("months_relevant", [])
             if not isinstance(m, int) or not 1 <= m <= 12]
for r in crop:
    for s in r.get("seasons", []):
        if s not in VALID_SEASON: bad_season.append((r["crop_en"], s))
    for m in r.get("planting_months", []) + r.get("harvest_months", []):
        if not isinstance(m, int) or not 1 <= m <= 12: bad_month.append((r["crop_en"], m))
if bad_season: fail(f"invalid season values: {bad_season[:5]}")
if bad_month: fail(f"invalid month values: {bad_month[:5]}")
print(f"  invalid seasons: {len(bad_season)}  invalid months: {len(bad_month)}")

# --------------------------------- 17. registration verification gate
print("\n[17] Registration verification gate (L1)")
pest = [p for p in prod if p["category"] == "pesticide"]
miss = [p["sku"] for p in pest if "registration_verified" not in p]
if miss: fail(f"pesticide SKUs without registration_verified: {miss[:5]}")
pv = sum(1 for p in pest if p.get("registration_verified"))
print(f"  pesticide SKUs: {len(pest)}  verified: {pv}  unverified: {len(pest)-pv}")
ctm = [(r["class_name"], ct.get("product_name_en")) for r in dis
       for ct in r.get("chemical_treatments", []) if "registration_verified" not in ct]
if ctm: fail(f"chemical treatments without registration_verified: {ctm[:5]}")
ctv = sum(1 for r in dis for ct in r.get("chemical_treatments", [])
          if ct.get("registration_verified"))
print(f"  chemical treatment entries: {ct_total}  verified: {ctv}  unverified: {ct_total-ctv}")
VERIFIED_AP = {"AP-2431","AP-384","AP-374","AP-460","AP-2312","AP-176",
               "AP-241","AP-354","AP-143","AP-3153","AP-252"}
bogus = []
for p in pest:
    for ap in p.get("verified_ap_numbers", []):
        if ap not in VERIFIED_AP: bogus.append((p["sku"], ap))
for r in dis:
    for ct in r.get("chemical_treatments", []):
        for ap in ct.get("verified_ap_numbers", []):
            if ap not in VERIFIED_AP: bogus.append((r["class_name"], ap))
if bogus: fail(f"AP numbers claimed verified but not in the verified set: {bogus[:5]}")
print(f"  AP numbers claimed verified outside the known-good set: {len(bogus)}")

# ------------------------------- 18. UI warning boxes referenced by LIMITS.md
print("\n[18] UI warning boxes present and bilingual (L2, L4, L5)")
boxes = {b["id"]: b for b in reg["ui_warning_boxes"]}
REQUIRED = ["warn_generic_pesticide","warn_phi","warn_hhp","warn_bee_safety",
            "warn_fish_safety","warn_no_cure_virus","warn_bacterial_not_fungal",
            "warn_healthy_no_spray","warn_low_confidence_crop",
            "warn_poisoning_emergency","warn_fake_product",
            "warn_price_indicative","warn_check_label",
            "warn_registration_unverified","warn_find_licensed_dealer"]
absent = [b for b in REQUIRED if b not in boxes]
if absent: fail(f"required UI warning boxes missing: {absent}")
nobn = [i for i, b in boxes.items()
        if not BN.search(b.get("title_bn","") + b.get("body_bn",""))]
if nobn: fail(f"warning boxes without Bangla: {nobn}")
print(f"  {len(boxes)} boxes; required present: {len(REQUIRED)-len(absent)}/{len(REQUIRED)}; without Bangla: {len(nobn)}")

print("\n[19] Disease step files — consecutive bilingual steps, model coverage")
from pathlib import Path as _P
_model = _P(__file__).resolve().parents[2] / "web" / "offline-pack.json"
if _model.exists():
    _classes = json.load(open(_model, encoding="utf-8"))["models"]["disease"]["classes"]
    _have = {r["class_name"] for r in dis}
    _miss = [c for c in _classes if c not in _have]
    if _miss:
        fail(f"model classes without a disease card: {len(_miss)} e.g. {_miss[:8]}")
    print(f"  model classes {len(_classes)}; pack {len(dis)}; missing {len(_miss)}")
else:
    print("  offline-pack.json not found — skip model coverage")
step_fail = 0
for r in dis:
    en, bn = r.get("immediate_actions_en") or [], r.get("immediate_actions_bn") or []
    if len(en) != len(bn) or len(en) < 3:
        fail(f"{r['class_name']}: steps en={len(en)} bn={len(bn)}")
        step_fail += 1
        continue
    for i, (a, b) in enumerate(zip(en, bn), 1):
        if a.get("step") != i or b.get("step") != i:
            fail(f"{r['class_name']}: steps not consecutive at {i}")
            step_fail += 1
            break
        if not BN.search(str(b.get("title", "")) + str(b.get("detail", ""))):
            fail(f"{r['class_name']}: step {i} missing Bangla")
            step_fail += 1
            break
print(f"  step-structure failures: {step_fail}")

# ------------------------------------------------------------------ summary
print("\n" + "=" * 78)
print("TARGETS VS DELIVERED")
print("=" * 78)
targets = [("A  diseases/*.json", 30, len(dis)),
           ("B  products.json", 200, len(prod)),
           ("C  equipment.json", 100, len(equip)),
           ("D  suppliers.json", 150, len(sup)),
           ("E  upazilas.json", 495, len(upz)),
           ("F  crop_profitability.json", 25, len(crop)),
           ("G  regulatory_safety.json", 1, len(reg["topics"])),
           ("H  order_workflow.json", 1, 1)]
EXPLAINED = {
    "D  suppliers.json": "DELIBERATE — only publicly documented entities included; no invented "
                         "phone numbers. Collection script provided to complete the 150.",
    "E  upazilas.json":  "The authoritative geocode dataset lists 494 upazilas, not 495. "
                         "All 494 delivered; the brief's 495 figure is out by one.",
}
for name, tgt, got in targets:
    mark = "MET" if got >= tgt else "SHORT"
    print(f"  {name:32} target {tgt:>4}   delivered {got:>4}   {mark}")
    if mark == "SHORT" and name in EXPLAINED:
        print(f"      -> {EXPLAINED[name]}")

print("\n" + "=" * 78)
print(f"FAILURES: {len(fails)}")
for f in fails: print("  FAIL " + f)
print(f"\nWARNINGS: {len(warns)}")
for w in warns: print("  WARN " + w)
print("=" * 78)
sys.exit(1 if fails else 0)
