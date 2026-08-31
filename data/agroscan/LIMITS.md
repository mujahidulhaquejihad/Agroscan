# AgroScan Data Pack — Known Limits

Nine limits, split by **who has to act**. Every one is already flagged inside the data; this file exists so nothing gets lost between the dataset and the product.

Two ways to read it: the table is the tracker, the sections below are the detail.

| # | Limit | Severity | Owner | Resolved when |
|---|---|---|---|---|
| L1 | Only 31 of 127 pesticide SKUs have a verified AP registration number | **BLOCKER** | DEV + UI | PPW registered list reconciled |
| L2 | Doses and PHIs are extension rates, not label transcriptions | **BLOCKER** | UI | `warn_check_label` shipped on every chemical card |
| L3 | The Bangla has never been reviewed by a Bangladeshi extension officer | **HIGH** | FIELD | Reviewed and corrections merged |
| L4 | No licensed private dealers — Section D is government and distributors only | **HIGH** | UI + DEV | Places collection run **and** licence-checked |
| L5 | Prices are indicative ranges, not quotes | **HIGH** | UI + DEV | Dealer price confirmation enforced in the order flow |
| L6 | HHP flags are hazard warnings, not a legal ban list | **HIGH** | DEV + UI | PPW cancelled list loaded as a separate table |
| L7 | Fertiliser doses are derived from FRG-2018, not transcribed from it | MEDIUM | DEV | FRG-2018 tables loaded as structured data |
| L8 | 12 upazila centroids borrow their parent upazila's point | MEDIUM | DEV | Surveyed points substituted, or radius logic gated |
| L9 | Section H has no primary survey behind it | MEDIUM | FIELD | 15–20 dealers and 40–50 farmers interviewed |

---

## Part 1 — What the UI must tell the farmer

These are not optional disclaimers. Each one prevents a specific way the app could mislead someone standing in a field.

### L2 · Doses and PHIs are extension rates, not label transcriptions — **BLOCKER**

The doses in this pack are the rates used across Bangladesh, cross-checked against BARI/BRRI/DAE guidance and, where possible, against the PPW registered list. They are **not** transcribed from the physical label of the specific pack a farmer buys, and label rates vary by product, formulation and crop.

**The label is the legal authority. The app is not.**

Ship **`warn_check_label`** (new, in `regulatory_safety.json`) on every `chemical_treatments` entry, next to `warn_phi`. It tells the farmer to read the pack and to follow the label if it differs.

> "স্প্রে করার আগে প্যাকেটের গায়ে লেখা মাত্রা ও ফসল তোলার নিরাপদ সময় সবসময় পড়ে নিন… লেবেলে অন্য কিছু লেখা থাকলে লেবেল অনুযায়ী চলুন।"

### L1 · Registration numbers — **BLOCKER**

31 of 127 pesticide SKUs and 30 of 62 chemical treatment entries now carry `registration_verified: true`. The rest are `false`.

**Do not render an AP number when `registration_verified` is false.** Show **`warn_registration_unverified`** instead. It says the active ingredient is registered in Bangladesh but that we could not confirm this specific product's number, and tells the farmer to check the pack for a printed number and a Bangla label.

Displaying an unconfirmed registration number as fact is a credibility problem and potentially a regulatory one.

### L5 · Prices are ranges

`price_bdt_min` / `price_bdt_max` are indicative spreads. Most carry `price_confidence: "low"`; fertiliser is `"medium"` because it is anchored to the government-fixed FY2025-26 rates plus the documented Tk 3–8/kg market premium.

Ship **`warn_price_indicative`** on every price and in the cart. It explicitly tells the farmer not to prepay on the strength of the displayed figure — which matters because Section H found prepayment is the app's riskiest assumption anyway.

### L4 · No licensed private dealers

Section D has 48 records: 15 Upazila Agriculture Offices, 15 Upazila Parishad nodes, 8 BADC district entries, 10 brand distributors. All `phone: null`, all `verified: false`.

Ship **`warn_find_licensed_dealer`** on the shop screen. It sends the farmer to the Upazila Agriculture Office for the licensed dealer register — a public list — and explains *why* a licensed dealer matters: you get a receipt you can complain with if the product turns out to be fake.

Every UAO record already carries this in `services_en` / `services_bn`, so you can surface it from the record rather than hard-coding it.

### L6 · HHP flags are hazard warnings, not a ban list

25 SKUs carry `highly_hazardous_flag: true`, drawn from a published national review of Highly Hazardous Pesticides. **These products may still be legally registered in Bangladesh.** Section G states this in `banned_or_restricted_reference.note_en`.

`warn_hhp` (already in the pack) is the right chip: "legally registered, but use it only when the problem justifies it, at label dose, with full protective equipment" — and it points the farmer at the lower-risk alternative shown above it in the same card.

**There is no verified banned list in this pack.** Until the PPW cancelled list is loaded, the app must not claim any product is banned.

---

## Part 2 — What the dev team must do before launch

### L1 · Reconcile registrations *(gate)*

Download the PPW **Registered** and **Cancelled** lists (`sources.json` → `ppw_registered_list`, `ppw_cancelled_list` — both `.gov.bd`, both blocked from the build sandbox, both should open from a normal browser in Bangladesh).

Then:
1. Set `registration_verified` from the official list, not from my 11 seed values.
2. Load the cancelled list as a **separate table** and hard-block any SKU on it.
3. Re-run `validate.py`.

The 11 currently verified numbers and their sources are listed in `SOURCES.md` §1 and `sources.json`.

### L6 · Banned-list handling

The HHP list and the cancelled list are different things and must be different tables. Conflating them will either over-warn on legal products or under-warn on illegal ones.

### L5 · Enforce dealer price confirmation

Section H's order state machine has `dealer_confirmed` requiring the dealer to confirm **price**, not just availability. Implement it that way. An order that goes firm on a catalogue price the shop does not honour loses the farmer on their first transaction.

### L7 · Fertiliser doses are derived

FRG-2018 was blocked from the build environment. The per-decimal doses in Sections A and F are derived from published FRG rates at medium soil fertility ÷ 247.1, not transcribed from the guide's tables. Marked `confidence: "medium"` throughout.

Load the real tables and replace the derivations. Also add the soil-fertility-level and Agro-Ecological Zone dimensions, which this pack flattens to "medium" everywhere.

### L8 · 12 low-confidence upazila centroids

These upazilas were created after the boundary dataset's vintage and borrow their parent upazila's interior point:

Guimara (2014) · Karnaphuli (2000) · Naldanga (2013) · Rangabali (2012) · Osmani Nagar (2013) · Tarakanda (2015) · Madhyanagar (2022) · Eidgaon (2021) · Dasar (2021) · plus 3 further partial matches

They carry `centroid_method: "parent_upazila_polygon"` and `confidence: "low"`. Directionally right, not surveyed.

**Fine for:** map defaults, "nearest upazila" sorting.
**Not fine for:** delivery radius, distance-based dealer ranking, anything a farmer sees as a distance in km.

Gate on `confidence != "low"` or substitute surveyed points. Full breakdown in `data/upazilas_qa.json`.

Also note: centroids are **interior representative points**, guaranteed inside the polygon but not town centres or upazila headquarters. Never use them for navigation.

---

## Part 3 — What needs people, not code

### L3 · The Bangla is unreviewed — **highest-value external check**

Every farmer-facing string has Bangla, written in farmer register rather than machine-translated: `প্রতি লিটার পানিতে ২.৫ গ্রাম`, not a transliteration of the English. Technical terms are handled the way extension material handles them.

**But it has never been read by a Bangladeshi agricultural extension officer, and never tested on a farmer.**

This is the single thing most likely to determine whether farmers trust the app. Commission a review by a Sub-Assistant Agriculture Officer or a DAE extension specialist — ideally someone who runs plant clinics — covering:

- the 58 disease cards' `immediate_actions_bn` (the text a farmer acts on)
- all 15 `ui_warning_boxes` (the safety copy)
- regional vocabulary — a term that reads naturally in Rangpur may not in Sylhet

### L9 · Section H is not field-validated

Section H describes how rural agro-input ordering works — payment, delivery, minimum orders, stock confirmation, returns, peak seasons, BADC vs private. It is compiled from documented supply-chain structure and published reporting. **It is not a primary survey**, and it says so in its own `confidence_statement`.

Its riskiest claim, and the one your product plan probably rests on: **farmers mostly will not prepay online.** Seasonal credit from the dealer they already owe money to is what actually governs where a farmer buys. A farmer in debt to his dealer is not free to shop elsewhere, whatever your app offers.

Validate before building the transaction layer, per §10 of `order_workflow.json`: 15–20 licensed dealers and 40–50 farmers across at least three Phase-1 upazilas covering different terrain (plain-land, char or haor, peri-urban).

If prepayment fails the test, the fallback is not a failure — an independent diagnosis naming an **active ingredient** and a dose, so a farmer can walk into any shop and ask for a specific thing instead of accepting whatever the dealer recommends and marks up, is arguably the bigger contribution anyway. And it requires nobody to change how they pay.

### L4 · Dealer collection is two steps, not one

`data/scripts/collect_dealers.py` gets you listings. It does **not** get you licensed dealers.

1. Run the script (needs `GOOGLE_MAPS_API_KEY`; read Google's caching and attribution policy first).
2. **Call every number.**
3. **Check each shop against the licensed dealer register at the Upazila Agriculture Office.**

A Google Maps listing is not proof of a pesticide dealer licence under the Pesticide Act 2018. Only set `verified: true` and `licence_status` after both checks. Until then the records stay out of the farmer-facing shop.

---

## What changed in the pack alongside this file

- `products.json` — added `registration_verified`, `verified_ap_numbers`, `registration_display_rule` (31 verified / 96 unverified / 110 n/a)
- `disease_treatments.json` — added `registration_verified` and `verified_ap_numbers` to all 62 chemical treatment entries (30 verified / 32 unverified)
- `regulatory_safety.json` — 4 new UI warning boxes, EN + BN: `warn_price_indicative`, `warn_check_label`, `warn_registration_unverified`, `warn_find_licensed_dealer` (15 total)

`validate.py` still passes with 0 failures and 0 warnings.
