# AgroScan — Bangladesh Agricultural Data Pack v1.0

Generated 2026-08-20. Bangladesh-only. English keys, Bangla (`_bn`) on every farmer-facing string.

---

## What you got

| Section | File | Brief's target | Delivered |
|---|---|---|---|
| A | `disease_treatments.json` | 30 diseases | **58** |
| B | `products.json` | 200 products | **237** |
| C | `equipment.json` | 100 items | **105** |
| D | `suppliers.json` | 150 dealers | **48** — see the honest caveat below |
| E | `upazilas.json` | 495 upazilas | **494** — the brief's 495 is out by one |
| F | `crop_profitability.json` | 25-30 crops | **30** |
| G | `regulatory_safety.json` | 1 reference doc | **9 topics + 11 UI warning boxes** |
| H | `order_workflow.json` | 1 doc | **1** |
| — | `keys_reference.json` | — | controlled vocabularies and join keys |
| — | `agroscan_master.json` | — | all sections in one file |

`validate.py` passes with **0 failures and 0 warnings**. Run it after any edit.

---

## Read this before you import anything

### 1. The brief's example numbers for potato are wrong by roughly 10x

The example record in the research brief shows potato at 800-1200 kg per **decimal** and a seed rate of 50-60 kg per decimal. Checked against BBS Yearbook of Agricultural Statistics 2024: potato was 10,601 thousand MT from 1,133 thousand acres in 2023-24, which is 23.1 t/ha — about **94 kg per decimal**, or 3,090 kg per bigha. The real Bangladeshi seed rate is 1.5-2.0 t/ha, about **7 kg per decimal**.

Most likely the example was written in per-bigha terms and labelled per-decimal. Everything in this pack is **per decimal**, and every crop record also carries the per-bigha figure because most farmers think in bigha or katha.

### 2. Section D contains no invented phone numbers, and that is deliberate

You asked for 150 dealers with real phone numbers. That data lives in Google Maps and Facebook listings; there is no public, citable dataset of Bangladeshi upazila agro-dealers, and the brief itself says not to invent numbers.

So Section D contains only entities whose existence is publicly documented: DAE Upazila Agriculture Offices for all 15 Phase-1 upazilas, Upazila Parishad contact nodes, BADC district presence, and the 10 national brand distributors whose names and AP registration numbers appear in the published DAE Plant Protection Wing registered pesticide list. Every record has `phone: null` and `verified: false`.

To complete it, run `data/scripts/collect_dealers.py`. It uses the Google Places API with Bangla and English query variants, dedupes by place_id, and writes records in the Section D schema. You need an API key. **Then do two things before showing any dealer to a farmer**: call the number, and check the shop against the licensed-dealer register held by the Upazila Agriculture Office. A Google listing is not proof of a pesticide dealer licence under the Pesticide Act 2018.

### 3. Prices are ranges and they will drift

`price_bdt_min` / `price_bdt_max` are indicative spreads, not quotes. Fertiliser is anchored to the government-fixed FY2025-26 farmer-level rates (urea 27, TSP 27, DAP 20, MoP 21 Tk/kg) with the documented Tk 3-8/kg real-market premium on the max. Everything else is estimated and carries `price_confidence: "low"`.

Section H explains why this matters: **the dealer must confirm the price in the order flow**, not just availability. If the app shows a price the shop does not honour, you lose the farmer on the first order.

### 4. Registration numbers: nine are verified, the rest are not

These AP numbers come from the published DAE Plant Protection Wing registered pesticide list and are **crop-matched or company-matched**:

| Product | AP no. | Holder | Registered use found |
|---|---|---|---|
| Karishma 28 SC | AP-2431 | Eon Trading House | **mango anthracnose** |
| Score 250 EC | AP-384 | Syngenta Bangladesh | **onion purple blotch** |
| Galben M | AP-374 | ACI Formulations | **potato & tomato late blight** |
| Contaf 5 EC | AP-460 | Auto Crop Care | **rice sheath blight** |
| Amistar Top | AP-2312 | Syngenta Bangladesh | **rice sheath blight, blast** |
| Bavistin DF | AP-176 | BASF Bangladesh | rice sheath blight, sugarcane |
| Knowin 50 WP | AP-241 | McDonald Bangladesh | rice sheath blight |
| Champion 77 WP | AP-354 | Petrochem Bangladesh | tomato blights |
| Rovral 50 WP | AP-143 | Bayer CropScience | mustard Alternaria spot |
| Sitro 25 SC | AP-3153 | S I Agro International | tea die-back |
| Microthiol Special 80 WP | AP-252 | Shetu Pesticides | tea mites |

Every other `registration_ref` says explicitly that the number was not individually verified. **Do not display a registration number the app cannot stand behind.** Pull the current list from PPW and reconcile before launch.

One known inconsistency: Champion 77 WP's active ingredient is reported as copper hydroxide in one extract of the PPW list and copper oxychloride in another. Confirm from the physical label.

### 5. There is no verified banned-pesticide list in this pack, on purpose

Press reporting citing DAE says 19 active ingredients have been banned since the 1960s, but the names are not published in any source reviewed. Rather than guess, Section G ships the **17 Highly Hazardous Pesticides** identified in a published national review, split into widely-used, moderately-used and registered-but-absent. These are **hazard flags, not a legal ban list** — products containing them may still be legally registered.

25 catalogue SKUs carry `highly_hazardous_flag: true`, and `warn_hhp` is the UI chip for them.

Get the actual cancelled/banned list from PPW before the app makes any "this product is banned" claim.

---

## App logic the data expects you to implement

These flags exist because getting them wrong causes real harm, not just a bad UX.

**`is_curable_with_chemicals: false`** — on TYLCV, tomato mosaic virus, tungro, citrus greening, chilli leaf curl and bacterial wilt. Show `no_cure_notice_en` / `_bn` **before** any product. On those classes every chemical entry also carries `cures_disease: false` and `targets_vector` naming the insect it actually kills. A farmer who sprays, sees no recovery and concludes the app lied is a farmer you have lost.

**Healthy classes carry zero chemical treatments.** All 15 of them. Show `warn_healthy_no_spray`.

**Bacterial classes must never route to a fungicide-only path.** Rice bacterial leaf blight, brinjal bacterial wilt, tomato and pepper bacterial spot. `warn_bacterial_not_fungal` exists for this. The dataset also declines to recommend agricultural antibiotics anywhere.

**14 guard classes** carry `bangladesh_relevance` of `not_grown`, `not_grown_commercially` or `rare_experimental` — apple, cherry, grape, peach, blueberry, raspberry. Show `warn_low_confidence_crop` and prompt a re-photograph instead of a treatment. `Apple___Cedar_apple_rust` is worth suppressing outright: it needs Eastern red cedar as an alternate host, which does not grow in Bangladesh, so that prediction is **biologically impossible** here.

**`kb_key` is not unique and that is intentional.** `late_blight` covers both potato and tomato because it is the same pathogen. Join products to diseases on `kb_key`; use `class_name` as the primary key.

**Substitute by active ingredient, never by trade name.** Dithane M-45 and Indofil M-45 are the same product. Section B is keyed on the active ingredient for exactly this reason.

---

## Cross-references are pre-resolved

`link_datasets.py` has already turned every product name reference into a SKU link. There is no runtime string matching to do.

- 226 `related_shop_products` references on disease cards → `related_shop_skus[]` with `sku`, `match_score`, `match_confidence`. **0 unresolved.**
- 126 `shop_products_needed` references on crop records → `sku` + `catalogue_name_en`. **0 unresolved.**
- All 30 Bangladesh-relevant treatable `kb_key`s have at least one linked shop product.

11 keys in `products.disease_keys` have no Section A card (`aphid`, `stem_borer`, `fruit_fly`, `rodent`, `nematode` and so on). That is not an error — they are arthropod and vertebrate pests the leaf-image model does not classify, and they exist so the shop can be browsed by problem. They are documented in `keys_reference.json` under `pest_keys`.

---

## Section E: how the geo data was built

The administrative hierarchy and Bangla names come from the `nuhil/bangladesh-geocode` dataset. Centroids come from geoBoundaries gbOpen BGD ADM3 polygons, joined by a transliteration-tolerant matcher (Bangladeshi place names are romanised inconsistently — Faridgonj/Faridganj, Senbug/Senbagh, Ukhiya/Ukhia) plus a greedy 64↔64 district reconciliation that handles the official renames (Bogra→Bogura, Jessore→Jashore, Comilla→Cumilla, Chittagong→Chattogram).

Result: 494 upazilas, 64 districts, 8 divisions. 420 high confidence, 62 medium, 12 low. Every point verified inside Bangladesh's bounding box, no duplicates.

The 12 low-confidence records are upazilas created **after** the boundary dataset's vintage — Guimara (2014), Karnaphuli (2000), Naldanga (2013), Rangabali (2012), Osmani Nagar (2013), Tarakanda (2015), Madhyanagar (2022), Eidgaon (2021), Dasar (2021). They borrow their parent upazila's interior point, are flagged `centroid_method: "parent_upazila_polygon"`, and say so in `notes`. Directionally right, not surveyed. Replace before using for delivery-radius logic.

Centroids are **interior representative points**, guaranteed to fall inside the polygon. They are not town centres or upazila headquarters. Fine for map defaults and distance sorting; not for navigation.

---

## Section F: what the economics actually say

Profit is **computed** from yield × price − cost, so the arithmetic always reconciles. Three scenarios per crop:

- `expected_profit_bdt_per_decimal_typical` — mid yield × mid price − mid cost. **Lead with this one.**
- `..._min` — min yield × min price − max cost. A bad year with high costs.
- `..._max` — max yield × max price − min cost. A good year with low costs.

Every one of the 30 crops has a negative `min`. That is not a modelling artefact; almost every crop in Bangladesh can lose money in a bad year, and the app should show that rather than hide it.

`profit_per_decimal_per_month_typical` is the field that makes the farm planner honest — it lets a 70-day mungbean be compared fairly against 12-month sugarcane. Ranked by it, the picture is: capsicum under polytunnel (~Tk 1,190/decimal/month) and vegetables at Tk 300-550, against Boro rice at Tk 14 and sugarcane at zero. Sugarcane's typical profit comes out at exactly zero without intercropping, which matches the well-documented state of Bangladeshi sugarcane economics.

For perennials (mango, banana, papaya, jackfruit) the input cost is **annual maintenance of a bearing plant** and excludes the 1-5 year establishment period. Do not compare them against annuals without accounting for that.

---

## Files

```
data/
  agroscan_master.json        all sections in one file
  disease_treatments.json     A — 58 records
  products.json               B — 237 SKUs
  equipment.json              C — 105 SKUs
  suppliers.json              D — 48 documented entities
  upazilas.json               E — 494 upazilas
  crop_profitability.json     F — 30 crops
  regulatory_safety.json      G — 9 topics, 11 UI warning boxes, helplines, portals
  order_workflow.json         H — ordering norms and a suggested order state machine
  keys_reference.json         controlled vocabularies and join keys
  upazilas_qa.json            geo match-quality QA report
  parts/                      Section A source files, merged into disease_treatments.json
  scripts/collect_dealers.py  Google Places dealer collection script
  _raw/                       upstream source data

build_upazilas.py    E: geocode ↔ geoBoundaries join
build_products.py    B: catalogue generator
build_equipment.py   C: catalogue generator
build_suppliers.py   D: documented-entity generator
build_crops.py       F: economics generator
link_datasets.py     cross-dataset SKU resolution + cure flags + keys reference
validate.py          16 integrity checks — run after any edit
```

Regenerate everything:

```bash
python3 build_upazilas.py && python3 build_products.py && \
python3 build_equipment.py && python3 build_suppliers.py && \
python3 build_crops.py && python3 link_datasets.py && python3 validate.py
```

---

## Before this reaches a farmer

1. **Get a Bangladeshi extension officer to review the Bangla.** It is written in farmer register, not machine-translated, but it has not been field-tested. This is the single highest-value review you can commission.
2. **Reconcile every AP registration number** against the current PPW list, and get the cancelled/banned list.
3. **Confirm dose and PHI against physical labels** for the products you actually recommend. The doses here are standard Bangladeshi extension rates; labels are the legal authority.
4. **Verify the 16358 DLS helpline number** and that each `dae.<upazila>.<district>.gov.bd` URL resolves.
5. **Validate Section H with fieldwork** before building the transaction layer. It is the least evidence-backed part of this pack, and its riskiest assumption — that farmers will prepay online — is one you should test before you build on it. Most will not; seasonal credit from the dealer they already owe money to is what actually governs where a farmer buys.

---

## Primary sources

- BBS *Yearbook of Agricultural Statistics 2024* — yields, area, production
- BARC *Fertilizer Recommendation Guide 2018* — fertiliser doses
- DAE Plant Protection Wing *Registered Pesticides List* — AP numbers, doses, registered crops
- *Pesticide Act 2018* and Pesticide Rules — registration and labelling
- *Food Safety (Contaminants, Toxins and Harmful Residues) Regulations 2017* — MRLs
- USDA FAS GAIN *Fertilizer Situation in Bangladesh* BG2025-0017 (30 Mar 2026) — FY2025-26 prices, consumption
- The Daily Star, *17 highly harmful pesticides widely used across country* — national HHP review
- Plantwise/CABI Bangladesh factsheets — brinjal shoot and fruit borer, mango anthracnose
- BRRI, BARI, BADC extension guidance; FAO *Eggplant IPM: An Ecological Guide*
- geoBoundaries gbOpen BGD ADM2/ADM3; `nuhil/bangladesh-geocode`

Every record carries its own `source` string. Where a claim could not be verified, `confidence` is `low` and `notes` says why.
