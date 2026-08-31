# AgroScan Data Pack — Source Register

Every URL behind the dataset, what it was used for, and **whether I could actually retrieve it**.

That last column matters. Several of the most authoritative Bangladeshi government documents could not be fetched from this environment — self-signed TLS certificates, robots.txt blocks, 403s. Where that happened I fell back on secondary sources and said so in the record's `confidence` and `notes`. **Those are the documents you should download yourself first.**

Legend: **✅ retrieved** — content read and used directly · **⚠️ partial** — retrieved but truncated or summarised · **❌ blocked** — found via search, could not fetch · **🔍 search-only** — known to exist, cited, not opened

---

## 1. Regulatory and pesticide registration

| Source | URL | Status | Used for |
|---|---|---|---|
| **DAE Plant Protection Wing — Registered Pesticides List** (Approved 66 PTAC & 95 PTASC-PPW) | `https://dae.portal.gov.bd/sites/default/files/files/dae.portal.gov.bd/page/8dbdf06a_3999_4ae5_bdfb_e441bc82b959/Approved%20(66%20PTAC%20&%2095%20PTASC-PPW)%20Registered%20Pesticides%20List.pdf` | ❌ blocked (TLS: self-signed cert) | The canonical AP registration list. **Download this first.** |
| **DAE PPW — List of Cancelled Pesticides** | `https://file-dhaka.portal.gov.bd/media/80b9a8cf-b0dc-4186-b545-f01a34a4f3a3/uploaded-files/approved-66-ptac-95-ptasc-ppw-registered-pesticidescancelled-list.pdf` | ❌ blocked | The de-registered/cancelled list. **This is the banned list you actually need.** |
| **Registered Pesticide in Bangladesh** (PTAC up to 65th meeting), Internet Archive full text | `https://archive.org/stream/RegisteredPesticideInBangladesh/Registered+pesticide+in+Bangladesh_djvu.txt` | ⚠️ partial | **All 11 verified AP numbers came from here** — Karishma 28 SC AP-2431, Score 250 EC AP-384, Galben M AP-374, Contaf 5 EC AP-460, Amistar Top AP-2312, Bavistin DF AP-176, Knowin 50 WP AP-241, Champion 77 WP AP-354, Rovral 50 WP AP-143, Sitro 25 SC AP-3153, Microthiol Special 80 WP AP-252 |
| — item page | `https://archive.org/details/RegisteredPesticideInBangladesh` | ✅ | Provenance: 119 pages, uploaded 2016 |
| **Bangladesh Crop Protection Association — Registered pesticide list to 2020** | `http://bcpabd.com/wp-content/uploads/2021/01/Registered-pesticide-List-of-Bangladesh-upto-2020.pdf` | ❌ 403 | Industry-side cross-check |
| **Pesticide Act 2018** (bdlaws) | `http://bdlaws.minlaw.gov.bd/upload/act/2025-01-29-15-56-34-107.বালাইনাশক--(পেস্টিসাইডস)-আইন,-২০১৮.pdf` | 🔍 | Legal framework, labelling and licensing requirements |
| **Bangladesh SPS Information Management System — Plant Protection** | `https://sps.apaari.org/index.php/plant-protection/` | ✅ | Act/Rules chronology; PPW address (Khamarbari, Farmgate, Dhaka-1215); `pqw.dae.gov.bd` portal |
| **USDA FAS GAIN — Food and Agricultural Import Regulations and Standards, Bangladesh** | `https://apps.fas.usda.gov/newgainapi/api/report/downloadreportbyfilename?filename=Food+and+Agricultural+Import+Regulations+and+Standards+Report_Dhaka_Bangladesh_4-15-2019.pdf` | ✅ | Registration process (dual application, ~2 years); MRLs follow Codex via Food Safety Regulations 2017 |
| **The Daily Star — "17 highly harmful pesticides widely used across country"** | `https://www.thedailystar.net/news/bangladesh/news/17-highly-harmful-pesticides-widely-used-across-country-4043486` | ✅ | **The entire HHP list in Section G** — 10 widely used, 7 moderately used, 8 registered-but-absent; the "19 banned since 1960" count; ">8,000 products registered with PPW"; paraquat banned in 40+ countries; 2020 BELA High Court petition |
| New Age — "Pesticide: banned, but sold" | `https://www.newagebd.net/post/opinion/255006/pesticide-banned-but-sold` | ❌ 403 | Corroboration (not used directly) |
| New Age — "Hazardous pesticides in wide use in Bangladesh" | `https://www.newagebd.net/article/50556/hazardous-pesticides-in-wide-use-in-bangladesh` | ❌ 403 | Corroboration (not used directly) |
| FAO/UN Bangladesh — FAO supports pesticide regulation strengthening | `https://bangladesh.un.org/en/263165-fao-supports-bangladesh-strengthening-pesticide-regulations` | 🔍 | Context for the ongoing regulatory reform |
| Food Safety (Contaminants, Toxins and Harmful Residues) Regulations 2017 | Bangladesh Food Safety Authority | 🔍 (via USDA GAIN) | MRL framework cited in every PHI note |

> **Action:** the two `.gov.bd` PDFs at the top are the highest-value downloads in this table. Until you have them, treat every unverified `registration_ref` as unverified.

---

## 2. Fertiliser doses and prices

| Source | URL | Status | Used for |
|---|---|---|---|
| **BARC Fertilizer Recommendation Guide 2018** (BARC portal) | `https://barc.portal.gov.bd/sites/default/files/files/barc.portal.gov.bd/page/4adead4d_6e17_4d74_b5bd_e86e46c059ad/88c1738fe0618daef286ef3d27c95423.pdf` | ❌ blocked (robots/TLS) | Crop-by-crop fertiliser doses. **Cited throughout Sections A and F; download and replace my per-decimal derivations with the real tables.** |
| — same document, MoA portal mirror | `https://moa.portal.gov.bd/sites/default/files/files/moa.portal.gov.bd/page/9d1b92d4_1793_43af_9425_0ed49f27b8d0/FRG-2018%20(English).pdf` | ❌ blocked (robots timeout) | Alternative mirror — try this one |
| — same document, BFA mirror | `https://www.bfa-fertilizer.org/wp-content/uploads/2019/09/Fertilizer-Recommendation-Guide-2018-English.pdf` | ❌ 404 | Dead link |
| **PLOS ONE — "Unbalanced fertilizer use in the Eastern Gangetic Plain"** | `https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272146` | ✅ | FRG-2018 vs FRG-2012 direction of change (N and K up, P down for rice; P −10 kg/ha and OM −2 t/ha for potato). Full rate tables are in its Supporting Information Table S7 |
| **USDA FAS GAIN — "Fertilizer Situation in Bangladesh" BG2025-0017**, 30 Mar 2026 | `https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Fertilizer+Situation+in+Bangladesh_Dhaka_Bangladesh_BG2025-0017` | ✅ | **FY2025-26 farmer-level prices: urea 27, TSP 27, DAP 20, MoP 21 Tk/kg.** FY2024/25 consumption: 5.9m MT total (urea 2.6m, TSP 0.765m, DAP 1.52m, MoP 1.01m) |
| **The Daily Star — "Farmers forced to pay more than subsidised rates"**, 28 Jan 2025 | `https://www.thedailystar.net/business/economy/news/farmers-forced-pay-more-subsidised-rates-fertiliser-3810946` | ✅ | **The Tk 3-8/kg real-market premium** applied to `price_bdt_max` on all fertiliser SKUs. Farmers paying urea 30-31, TSP 35, DAP 24. Dealer commission Tk 2, fixed in 2008 |
| The Daily Star — "Fertiliser prices raised by Tk 5 per kg" | `https://www.thedailystar.net/news/bangladesh/agriculture/news/fertiliser-prices-raised-tk-5-kg-3294291` | ✅ | The April 2023 price order — dealer-level urea 25 / DAP 19 / TSP 25 / MOP 18; farmer-level 27/21/27/20 |

> **Known discrepancy, flagged in the data:** USDA FY2025-26 gives DAP 20 / MoP 21; the Jan 2025 Daily Star gives DAP 21 / MoP 20. I used the USDA figures as more recent. Confirm with MoA.

---

## 3. Yields, area and production (Section F)

| Source | URL | Status | Used for |
|---|---|---|---|
| **BBS Yearbook of Agricultural Statistics 2024** | `https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs/2024/12/58f325576f9a47cc91e7d227e336e40f.pdf` | ✅ | **The yield anchor for all 30 crops.** 2023-24 area ('000 acres) and production ('000 MT) |
| — BBS landing page | `https://bbs.gov.bd/site/page/3e838eb6-30a2-4709-be85-40484b0c16c6/Yearbook-of-Agricultural-Statistics` | 🔍 | Newer editions |
| BBS Agriculture section | `https://bbs.gov.bd/site/page/453af260-6aea-4331-b4a5-7b66fe63ba61/Agriculture` | 🔍 | Other agricultural series |
| SDG portal — 45 years Agriculture Statistics of Major Crops | `https://sdg.gov.bd/uploads/resources/attachment_a2a58baadb6c24399ef49150f268a92a.pdf` | 🔍 | Long-run trend cross-check |

**⚠️ Important correction I made to this source.** The extraction of the BBS summary table initially reported Boro yield as 5.16 t/ha. That does not reconcile with the area and production on the same page. Recomputing from the primary figures:

| Crop | Area ('000 ac) | Prod ('000 MT) | → t/ha | → kg/decimal |
|---|---|---|---|---|
| Boro rice | 12,052 | 21,068 | **4.32** | 17.5 |
| Aman rice | 14,210 | 16,656 | **2.90** | 11.7 |
| Aus rice | 2,557 | 2,973 | **2.87** | 11.6 |
| Wheat | 770 | 1,171 | **3.76** | 15.2 |
| Maize | 1,270 | 4,876 | **9.49** | 38.4 |
| Potato | 1,133 | 10,601 | **23.12** | 93.6 |
| Tomato | 76 | 491 | **15.96** | 64.6 |
| Onion | 513 | 2,917 | **14.05** | 56.9 |
| Sugarcane | 167 | 2,934 | **43.41** | 175.7 |

Conversions: 1 ha = 2.471 acres; 1 ha = 247.1 decimal. Rice figures are clean rice. **These recomputed values are what Section F uses** — re-verify against the PDF's own yield column when you have it open.

---

## 4. Market prices

| Source | URL | Status | Used for |
|---|---|---|---|
| **Department of Agricultural Marketing — daily price portal** | `https://market.dam.gov.bd/?L=E` | ⚠️ partial | Live wholesale/retail reference. **The interactive report requires division/district/upazila selection — build a scraper against it rather than the static PDF** |
| — daily price report (static PDF) | `https://market.dam.gov.bd/global/custom_files/daily_price_report.pdf` | ⚠️ partial | Stale (returned a 2024 date); structure only |
| — graphical report | `https://market.dam.gov.bd/price_graphical_report?L=E` | 🔍 | Price trend series |
| — manage/daily price report | `https://market.dam.gov.bd/market_daily_price_report?L=E` | ⚠️ partial | Rice 47-75 Tk/kg band and similar indicative ranges |
| DAM main portal | `http://dam.portal.gov.bd/` | 🔍 | Department landing page |

> **Farm-gate prices in Section F are estimated below the DAM retail/wholesale levels.** DAM publishes what the consumer and the wholesaler pay, not what the farmer receives. Every price field carries `price_confidence: "low"`. Wire the app to this portal and refresh seasonally.

---

## 5. Crop protection — disease and pest management

| Source | URL | Status | Used for |
|---|---|---|---|
| **Plantwise factsheet — Shoot and fruit borer of brinjal** (Bangladesh, SPIED, Sept 2013) | `https://factsheetadmin.plantwise.org/Uploads/PDFs/20157800236.pdf` | ✅ | **40-60 pheromone traps/acre**; tolerant varieties **Jhumka, Shingnath, Nayantara, Uttara**; flubendiamide (Belt) every 15 days; intercrop cowpea/maize/coriander |
| Plantwise Knowledge Bank — Propiconazole to control anthracnose in mango | `https://plantwiseplusknowledgebank.org/doi/full/10.1079/pwkb.20167800026` | ❌ 403 | Cited in mango anthracnose `source` |
| CABI — PlantwisePlus in Bangladesh | `https://www.cabi.org/wp-content/uploads/PlantwisePlus_in_Bangladesh-2.pdf` | 🔍 | Programme context; plant clinic network |
| PlantwisePlus blog — plant clinics in Bangladesh | `https://blog.plantwise.org/2026/02/24/in-photos-advisory-services-in-bangladesh/` | 🔍 | Extension delivery context |
| **FAO — Eggplant IPM: An Ecological Guide** | `https://openknowledge.fao.org/server/api/core/bitstreams/fe47c702-b9bf-4f5a-97bc-4d8d8dc1a541/content` | 🔍 | Brinjal bacterial wilt and BSFB IPM |
| **Vegetable IPM in Bangladesh** — Radcliffe's IPM World Textbook (Rahman) | `https://ipmworld.umn.edu/rahman` | 🔍 | Bangladesh-specific vegetable IPM; grafting on wilt-resistant rootstock |
| BPS — Survey on rice blast in Bangladesh and in-vitro fungicide evaluation | `http://bps.net.bd/wp-content/uploads/2020/12/9.-SURVEY-ON-RICE-BLAST-IN-SOME-SELECTED-AREA-OF-BANGLADESH-AND-IN-VITRO-EVALUATION-OF-FUNGICIDES-AGAINST-PYRICULARIA-ORYZAE.pdf` | ❌ redirect loop | Cited in rice blast `source` |
| DAE Bochaganj (Dinajpur) — rice blast control notice | `http://dae.bochaganj.dinajpur.gov.bd/en/site/news/XGnv-ধানের-ব্লাষ্ট-প্রতিরোধ-করণীয়` | ❌ proxy 403 | Example of upazila-level DAE advisories — **a good scrape target for Bangla extension text** |
| Trichoderma harzianum vs potato late/early blight | `https://www.sciencedirect.com/science/article/pii/S2773078623000286` | 🔍 | Biocontrol efficacy in Bangladesh |
| Control of late blight of potato (GGF Journals) | `https://ggfjournals.com/assets/uploads/10-151.pdf` | ❌ robots | Fungicide trial data |
| World Potato Congress — Potato Late Blight Warning System in Bangladesh | `https://potatocongress.org/potato-late-blight-warning-system-in-bangladesh/` | 🔍 | National blight forecasting |
| Tomato pests and diseases in Bangladesh and India, *Int. J. Pest Management* | `https://www.tandfonline.com/doi/full/10.1080/09670874.2023.2252760` | 🔍 | TYLCV, whitefly, farmer practice, IPM economics |
| Tomato Cultivation in Bangladesh: Pest Awareness and Disease Management | ResearchGate 391850970 | 🔍 | Bangladeshi tomato disease practice |
| Cultivating Profitable and Nutritious Tomatoes (Bangladesh guide) | ResearchGate 389900612 | 🔍 | Tomato agronomy |
| BARI Tomato-4 under polytunnel, *Arch. Agric. Environ. Sci.* | `https://doi.org/10.26832/24566632.2024.0904011` | 🔍 | Summer polytunnel tomato |
| Management of BSFB using selected insecticides, Bangladesh | ResearchGate 319322900 | 🔍 | BSFB insecticide efficacy and resistance |
| Present Scenario of Insecticides and Fungicides Use in Largest Mango Cultivation Area in Bangladesh | `https://www.academia.edu/25079065/` | 🔍 | Mango spray practice in Chapainawabganj |
| Wheat production under climate change: a Bangladesh perspective (Springer) | `https://link.springer.com/chapter/10.1007/978-981-13-6883-7_24` | 🔍 | Wheat blast since 2016; BARI Gom 33 |
| The Asian Age — BLB and blast-resistant rice varieties: BRRI's breakthrough | `https://dailyasianage.com/news/351095/` | 🔍 | BRRI resistant variety releases |
| Krishi Projukti Hatboi (BARI Agricultural Technology Handbook), 9th ed. 2019 | `https://www.scribd.com/document/670389244/` | ❌ paywall | **The definitive BARI crop-by-crop handbook — get the official PDF from BARI** |

---

## 6. Institutions and helplines (Section G)

| Source | URL | Status | Used for |
|---|---|---|---|
| **Krishi Call Center 16123** — FAO STI Portal | `https://sti-portal.fao.org/innovations/krishi-call-center-16123-bangladesh` | ✅ | Confirms 16123 as the DAE/AIS farmer helpline |
| Farmers' exposure to Krishi Call Center (16123) of AIS | ResearchGate 391849059 | 🔍 | Usage patterns |
| Agriculture Information Service (AIS) | `https://en.wikipedia.org/wiki/Agriculture_Information_Service` | 🔍 | AIS operates the call centre |
| Department of Agricultural Extension | `https://dae.gov.bd` | 🔍 | Institutional |
| BARC | `https://barc.gov.bd` | 🔍 | FRG publisher |
| BARI | `https://bari.gov.bd` | 🔍 | Non-rice crop research |
| BRRI | `https://brri.gov.bd` | 🔍 | Rice varieties, AWD, disease guidance |
| BADC | `https://badc.gov.bd` | 🔍 | Certified seed, fertiliser, irrigation |
| Ministry of Agriculture | `https://moa.gov.bd` | 🔍 | Policy, FRG mirror |
| BAMIS (agro-meteorology) | `https://bamis.gov.bd` | 🔍 | Weather advisories — **worth integrating for blight forecasting** |
| BADC seed / call centre listing example | `https://seedsbadc.netrokona.gov.bd/en/site/page/মোবাইল-সেবার-তালিকা-:-কল-সেন্টার` | 🔍 | Example of district BADC presence |

> **16358 (Department of Livestock Services) is taken from your brief and was not independently verified.** It is flagged `confidence: "medium"` in `regulatory_safety.json`. Confirm with DLS.

---

## 7. Geographic data (Section E)

| Source | URL | Status | Used for |
|---|---|---|---|
| **nuhil/bangladesh-geocode** | `https://github.com/nuhil/bangladesh-geocode` | ✅ | Division/district/upazila hierarchy + **official Bangla names**. Files used: `divisions/divisions.json`, `districts/districts.json` (with lat/lon), `upazilas/upazilas.json` (494 records, no coordinates) |
| — raw upazilas | `https://raw.githubusercontent.com/nuhil/bangladesh-geocode/master/upazilas/upazilas.json` | ✅ | 494 records with `bn_name` and `.gov.bd` URL |
| — raw districts | `https://raw.githubusercontent.com/nuhil/bangladesh-geocode/master/districts/districts.json` | ✅ | 64 districts with lat/lon |
| — raw divisions | `https://raw.githubusercontent.com/nuhil/bangladesh-geocode/master/divisions/divisions.json` | ✅ | 8 divisions |
| **geoBoundaries gbOpen BGD ADM3** (upazila polygons) | `https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/BGD/ADM3/geoBoundaries-BGD-ADM3_simplified.geojson` | ✅ | **544 upazila polygons → interior representative points.** Note: the `raw.githubusercontent.com` path returns a Git LFS pointer; use the `media.` host |
| **geoBoundaries gbOpen BGD ADM2** (district polygons) | `https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/BGD/ADM2/geoBoundaries-BGD-ADM2_simplified.geojson` | ✅ | 64 district polygons for point-in-polygon assignment |
| geoBoundaries project | `https://www.geoboundaries.org` | ❌ API blocked | Attribution and licence |
| ifahimreza/bangladesh-geojson | `https://github.com/ifahimreza/bangladesh-geojson` | ✅ | Cross-check (494 upazilas confirmed); no coordinates either |

**Match quality:** 415 exact name-in-district, 56 fuzzy, 9 parent-polygon (post-vintage upazilas), 5 manual override, 9 partial. 420 high / 62 medium / 12 low confidence. Full breakdown in `data/upazilas_qa.json`.

---

## 8. Section D — supply side

| Source | URL | Status | Used for |
|---|---|---|---|
| DAE upazila office subdomains (pattern) | `https://dae.<upazila>.<district>.gov.bd` — e.g. `dae.savar.dhaka.gov.bd`, `dae.trishal.mymensingh.gov.bd` | 🔍 **pattern not individually verified** | 15 Upazila Agriculture Office records. **Verify each resolves; phone numbers are published on these pages and should be scraped from there** |
| Confirmed live examples of the pattern | `dae.bochaganj.dinajpur.gov.bd`, `dae.jagannathpur.sunamganj.gov.bd` | ✅ (via search results) | Evidence the pattern is real |
| Bangladesh national portal | `https://bangladesh.gov.bd` | 🔍 | Upazila Parishad / Union Digital Centre structure |
| DAE PPW registered list (as above) | — | ⚠️ partial | The 10 brand-distributor records and their AP numbers |
| **Google Places API (New) — Text Search** | `https://places.googleapis.com/v1/places:searchText` | ⛔ **not called** | The route to real dealers. `data/scripts/collect_dealers.py` is written and ready; needs `GOOGLE_MAPS_API_KEY`. Read Google's caching/attribution policy before storing results |

---

## 9. Section C — equipment

No single citable price list exists for Bangladeshi farm machinery retail. Prices are **indicative 2025-26 retail ranges** compiled from general market knowledge, carrying `price_confidence: "low"` on all 105 SKUs. Machine designs referenced: BRRI rotary/cono weeder and AWD field water tube; BARI mango harvester pole and solar tunnel dryer; BJRI jute ribboner. Subsidy eligibility (17 SKUs flagged) reflects the MoA agricultural mechanisation programme — **percentages and eligible machine lists change by fiscal year and region; verify with DAE.**

---

## 10. Class list

PlantVillage-style `Crop___Condition` labels, matching the ~38-class public dataset convention plus Bangladesh-specific additions (Brinjal, Chilli, Wheat blast, Banana Sigatoka, Onion purple blotch, Rice BLB/sheath blight/tungro). Cross-referenced against BBS 2024 to determine which crops are actually grown here — that check produced the 14 `bangladesh_relevance` guard classes.

---

## What to download first

Ranked by how much of the dataset's uncertainty each one removes:

1. **DAE PPW Registered Pesticides List** + **Cancelled list** → converts ~50 unverified `registration_ref` strings into verified ones, and gives you the real banned list
2. **BARC FRG-2018** → replaces my per-decimal derivations with the authoritative tables
3. **BARI Krishi Projukti Hatboi (9th ed.)** → the definitive Bangla crop-by-crop reference; would let a reviewer check every disease card against national guidance
4. **BBS Yearbook 2024, yield tables** → confirm my recomputed t/ha figures
5. **DAM daily price feed** → replaces every estimated price with live data
6. **Upazila DAE office pages** → real phone numbers for Section D, legitimately and for free

Items 1, 2 and 6 are all `.gov.bd` and blocked from this sandbox but should open fine from a normal browser in Bangladesh.
