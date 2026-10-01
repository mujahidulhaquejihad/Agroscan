# AgroScan — Verified working source links

Checked live on **2026-08-23**. Use this list for demos / viva. Prefer these over older broken `.gov.bd` PDF paths in `SOURCES.md`.

Status legend:
- **OK** — HTTP 200 from this environment (or opened successfully via browser fetch)
- **OFFICIAL LIVE PORTAL** — interactive site that is the current authority (better than a stale PDF)

---

## A. Pesticide registration (most important for treatments)

| What | Link | Status | How to verify data |
|---|---|---|---|
| **PPW Pesticide Information Repository (official live list)** | https://ppw.krishi.gov.bd/ | OK | Search product / AP number; export PDF/CSV |
| **PPW pesticide list page** | https://ppw.krishi.gov.bd/pesticide-list | OK | Same repository UI |
| **PRISM dealer / marketed pesticide list** | https://prism.dae.gov.bd/pesticide-list | OK | Filter by region / district / upazila |
| **Internet Archive — Registered Pesticide in Bangladesh** (pack used this for 11 verified AP nos.) | https://archive.org/details/RegisteredPesticideInBangladesh | OK | Open item; text mirror also OK |
| Archive full text | https://archive.org/stream/RegisteredPesticideInBangladesh/Registered+pesticide+in+Bangladesh_djvu.txt | OK | Search AP-374, AP-384, etc. |
| BCPA registered list (to 2020) | http://bcpabd.com/wp-content/uploads/2021/01/Registered-pesticide-List-of-Bangladesh-upto-2020.pdf | OK | Industry cross-check |
| Daily Star — 17 HHPs widely used | https://www.thedailystar.net/news/bangladesh/news/17-highly-harmful-pesticides-widely-used-across-country-4043486 | OK | Source for HHP flags (not a legal ban list) |
| FAO/UN — pesticide regulation strengthening | https://bangladesh.un.org/en/263165-fao-supports-bangladesh-strengthening-pesticide-regulations | OK | Policy context |
| SPS plant protection page | https://sps.apaari.org/index.php/plant-protection/ | OK | Act/Rules chronology, PPW contact |
| Pesticide Act 2018 portal | http://bdlaws.minlaw.gov.bd/ | OK | Legal framework landing |
| USDA FAS — FAIRS Bangladesh | https://apps.fas.usda.gov/newgainapi/api/report/downloadreportbyfilename?filename=Food+and+Agricultural+Import+Regulations+and+Standards+Report_Dhaka_Bangladesh_4-15-2019.pdf | OK | Registration process / MRL context |

**Broken / unreliable (do not cite as primary):**
- Old DAE portal “Approved 66 PTAC…” PDF path — fails (TLS / unavailable)
- Old cancelled-list `file-dhaka.portal.gov.bd` PDF — fails
- Another DAE static PDF sometimes returns 503 — use **ppw.krishi.gov.bd** instead

**How to verify a product from AgroScan:** open https://ppw.krishi.gov.bd/pesticide-list → search trade name or AP number → confirm crop/pest matches the disease card.

---

## B. Fertilizer recommendations & prices

| What | Link | Status | Notes |
|---|---|---|---|
| **BARC Fertilizer Recommendation Guide 2024 (official PDF)** | http://apps.barc.gov.bd/fertilizer_recommendation/FRG%20English%2030.10.2024.pdf | OK | Prefer this over FRG-2018 dead links |
| BARC home | https://barc.gov.bd | OK | Publisher |
| PLOS ONE — unbalanced fertilizer use (Eastern Gangetic Plain) | https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272146 | OK | Academic cross-check of FRG direction |
| USDA FAS — Fertilizer Situation in Bangladesh | https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Fertilizer+Situation+in+Bangladesh_Dhaka_Bangladesh_BG2025-0017 | OK | FY farmer-level urea/TSP/DAP/MoP prices |
| Daily Star — farmers pay above subsidy | https://www.thedailystar.net/business/economy/news/farmers-forced-pay-more-subsidised-rates-fertiliser-3810946 | OK | Market premium context |

**Broken:** old FRG-2018 BARC/MoA portal PDF mirrors — fail from this environment.

---

## C. Yields / agricultural statistics

| What | Link | Status | Notes |
|---|---|---|---|
| BBS Yearbook of Agricultural Statistics 2024 (PDF used in pack) | https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs/2024/12/58f325576f9a47cc91e7d227e336e40f.pdf | OK | Yield anchors |
| BBS yearbook landing page | https://bbs.gov.bd/site/page/3e838eb6-30a2-4709-be85-40484b0c16c6/Yearbook-of-Agricultural-Statistics | OK | Official catalogue |
| BBS Agriculture section | https://bbs.gov.bd/site/page/453af260-6aea-4331-b4a5-7b66fe63ba61/Agriculture | OK | Related series |
| BBS home | https://bbs.gov.bd/ | OK | |

---

## D. Market prices

| What | Link | Status |
|---|---|---|
| DAM daily market prices | https://market.dam.gov.bd/?L=E | OK |
| DAM portal | http://dam.portal.gov.bd/ | OK |

---

## E. Disease / IPM references (sample working links)

| What | Link | Status |
|---|---|---|
| Plantwise — Brinjal shoot & fruit borer PDF | https://factsheetadmin.plantwise.org/Uploads/PDFs/20157800236.pdf | OK |
| Potato late blight warning system (BD) | https://potatocongress.org/potato-late-blight-warning-system-in-bangladesh/ | OK |
| FAO eggplant IPM guide | https://openknowledge.fao.org/server/api/core/bitstreams/fe47c702-b9bf-4f5a-97bc-4d8d8dc1a541/content | OK |
| Vegetable IPM in Bangladesh (UMN) | https://ipmworld.umn.edu/rahman | OK (opens; some clients may get 403) |
| Asian Age — BLB/blast-resistant rice | https://dailyasianage.com/news/351095/ | OK |

---

## F. Institutions & helplines

| Org | Link | Status |
|---|---|---|
| DAE | https://dae.gov.bd | OK |
| BARI | https://bari.gov.bd | OK |
| BRRI | https://brri.gov.bd | OK |
| BARC | https://barc.gov.bd | OK |
| MoA | https://moa.gov.bd | OK |
| BADC | https://badc.gov.bd | OK |
| BAMIS | https://bamis.gov.bd | OK |
| Krishi Call Center 16123 | https://sti-portal.fao.org/innovations/krishi-call-center-16123-bangladesh | OK |

---

## G. Geography (district / upazila)

| What | Link | Status |
|---|---|---|
| bangladesh-geocode (names) | https://github.com/nuhil/bangladesh-geocode | OK |
| Raw upazilas JSON | https://raw.githubusercontent.com/nuhil/bangladesh-geocode/master/upazilas/upazilas.json | OK |
| geoBoundaries | https://www.geoboundaries.org/ | OK |

---

## How to answer “are your treatments verifiable?”

1. **Product / AP number** → https://ppw.krishi.gov.bd/pesticide-list (live official list)  
2. **Dose / crop** → same PPW entry + product label; pack marks many AP refs as *not individually verified*  
3. **Fertilizer advice** → FRG-2024 PDF above  
4. **Yields** → BBS yearbook PDF above  
5. **Per-disease narrative in AgroScan** → `data/agroscan/diseases/<class>.json`, one file per disease (each record has `source`, `confidence`, `last_verified`); chat RAG reads these same files in memory

### Honest limits (say this if asked)
- Not every chemical line in the pack has a verified AP number; only ~11 were matched to the Archive register.  
- HHP flags come from press/research reporting, **not** a complete legal ban list.  
- Prices are indicative ranges; dealer confirms at order time.  
- Always tell farmers: follow the printed label and ask the upazila agriculture office / 16123.
