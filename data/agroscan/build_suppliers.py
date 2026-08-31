#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgroScan Section D — build suppliers.json

WHAT THIS FILE IS AND IS NOT
----------------------------
The original brief asked for the top 10 agro-input dealers per upazila with real
phone numbers. That data does not exist in any public, citable dataset. It lives
in Google Maps and Facebook listings, which cannot be scraped from this
environment, and the brief itself forbids inventing phone numbers.

So this file contains ONLY entities whose existence is publicly documented:

  1. DAE Upazila Agriculture Offices — every upazila has one, each with an
     official gov.bd subdomain following the pattern dae.<upazila>.<district>.gov.bd.
     These are the correct first point of contact for a farmer and they also
     hold the licensed-dealer register for the upazila.
  2. Upazila Parishad / Union Digital Centre — the general government service
     point, used here as a fallback contact node.
  3. BADC seed and fertiliser distribution points where a district-level BADC
     presence is documented.
  4. National brand distributors whose names appear in the DAE Plant Protection
     Wing registered pesticide list, as "who makes the product you were
     recommended" rather than "where to buy it locally".

Every record has phone: null and verified: false unless a number has been
confirmed. The dev team must fill in real dealers via the collection script in
scripts/collect_dealers.py, which uses the Google Places API and requires a key.

This is deliberately a smaller, honest dataset rather than 150 invented rows.
"""
import json

D = "/root/agroscan/data/"
TODAY = "2026-08-20"

# Phase 1 upazilas from the brief, with the Bangla names and the centroid taken
# from the Section E dataset so the two files agree.
PHASE1 = [
    ("Dhaka", "ঢাকা", "Savar", "সাভার", "dae.savar.dhaka.gov.bd"),
    ("Dhaka", "ঢাকা", "Dhamrai", "ধামরাই", "dae.dhamrai.dhaka.gov.bd"),
    ("Dhaka", "ঢাকা", "Keraniganj", "কেরাণীগঞ্জ", "dae.keraniganj.dhaka.gov.bd"),
    ("Gazipur", "গাজীপুর", "Kaliakair", "কালিয়াকৈর", "dae.kaliakair.gazipur.gov.bd"),
    ("Gazipur", "গাজীপুর", "Kapasia", "কাপাসিয়া", "dae.kapasia.gazipur.gov.bd"),
    ("Mymensingh", "ময়মনসিংহ", "Trishal", "ত্রিশাল", "dae.trishal.mymensingh.gov.bd"),
    ("Mymensingh", "ময়মনসিংহ", "Gafargaon", "গফরগাঁও", "dae.gafargaon.mymensingh.gov.bd"),
    ("Rajshahi", "রাজশাহী", "Paba", "পবা", "dae.paba.rajshahi.gov.bd"),
    ("Rajshahi", "রাজশাহী", "Tanore", "তানোর", "dae.tanore.rajshahi.gov.bd"),
    ("Khulna", "খুলনা", "Dumuria", "ডুমুরিয়া", "dae.dumuria.khulna.gov.bd"),
    ("Khulna", "খুলনা", "Digholia", "দিঘলিয়া", "dae.digholia.khulna.gov.bd"),
    ("Sylhet", "সিলেট", "Golapganj", "গোলাপগঞ্জ", "dae.golapganj.sylhet.gov.bd"),
    ("Sylhet", "সিলেট", "Beanibazar", "বিয়ানীবাজার", "dae.beanibazar.sylhet.gov.bd"),
    ("Barisal", "বরিশাল", "Babuganj", "বাবুগঞ্জ", "dae.babuganj.barisal.gov.bd"),
    ("Rangpur", "রংপুর", "Badargonj", "বদরগঞ্জ", "dae.badargonj.rangpur.gov.bd"),
]

# National brand distributors, taken from company names that appear in the
# published DAE Plant Protection Wing registered pesticide list.
BRANDS = [
    ("ACI Formulations Limited", "এসিআই ফরমুলেশনস লিমিটেড",
     ["Galben M (AP-374)"], ["pesticide", "seed", "fertilizer"],
     "Registration holder for Galben M (AP-374), registered for potato and tomato late blight."),
    ("Syngenta Bangladesh Limited", "সিনজেনটা বাংলাদেশ লিমিটেড",
     ["Score 250 EC (AP-384)", "Amistar Top (AP-2312)", "Actara 25 WG"],
     ["pesticide", "seed"],
     "Registration holder for Score 250 EC (AP-384, onion purple blotch) and Amistar Top (AP-2312, rice sheath blight and blast)."),
    ("BASF Bangladesh Limited", "বিএএসএফ বাংলাদেশ লিমিটেড",
     ["Bavistin DF (AP-176)"], ["pesticide"],
     "Registration holder for Bavistin DF (AP-176), registered for rice sheath blight and sugarcane."),
    ("Auto Crop Care Limited", "অটো ক্রপ কেয়ার লিমিটেড",
     ["Contaf 5 EC (AP-460)"], ["pesticide"],
     "Registration holder for Contaf 5 EC (AP-460), registered for rice sheath blight."),
    ("Petrochem (Bangladesh) Limited", "পেট্রোকেম (বাংলাদেশ) লিমিটেড",
     ["Champion 77 WP (AP-354)"], ["pesticide"],
     "Registration holder for Champion 77 WP (AP-354), registered for tomato blights."),
    ("Eon Trading House", "ইওন ট্রেডিং হাউস",
     ["Karishma 28 SC (AP-2431)"], ["pesticide"],
     "Registration holder for Karishma 28 SC (AP-2431), registered for mango anthracnose."),
    ("McDonald Bangladesh (Pvt) Limited", "ম্যাকডোনাল্ড বাংলাদেশ (প্রা.) লিমিটেড",
     ["Knowin 50 WP (AP-241)"], ["pesticide"],
     "Registration holder for Knowin 50 WP (AP-241), registered for rice sheath blight."),
    ("Shetu Pesticides Limited", "সেতু পেস্টিসাইডস লিমিটেড",
     ["Microthiol Special 80 WP (AP-252)"], ["pesticide"],
     "Registration holder for Microthiol Special 80 WP (AP-252)."),
    ("S I Agro International", "এস আই এগ্রো ইন্টারন্যাশনাল",
     ["Sitro 25 SC (AP-3153)"], ["pesticide"],
     "Registration holder for Sitro 25 SC (AP-3153)."),
    ("Bayer CropScience Limited", "বায়ার ক্রপসায়েন্স লিমিটেড",
     ["Rovral 50 WP (AP-143)", "Nativo 75 WG"], ["pesticide"],
     "Registration holder for Rovral 50 WP (AP-143), registered for mustard Alternaria spot."),
]

recs = []


def add(r):
    r.setdefault("email", None)
    r.setdefault("verified", False)
    r.setdefault("delivery_available", None)
    r.setdefault("payment_methods", [])
    r.setdefault("last_verified", TODAY)
    r.setdefault("notes", "")
    recs.append(r)


# ---- 1. DAE Upazila Agriculture Offices -------------------------------
for dist, dist_bn, upa, upa_bn, url in PHASE1:
    add({
        "name_en": f"Upazila Agriculture Office, {upa} (Department of Agricultural Extension)",
        "name_bn": f"উপজেলা কৃষি অফিস, {upa_bn} (কৃষি সম্প্রসারণ অধিদপ্তর)",
        "type": "government_office",
        "phone": None,
        "address_en": f"Upazila Parishad complex, {upa}, {dist}",
        "address_bn": f"উপজেলা পরিষদ চত্বর, {upa_bn}, {dist_bn}",
        "district": dist,
        "upazila": upa,
        "rank_in_upazila": 1,
        "rating": None,
        "products_sold": [],
        "services_en": [
            "Free crop, pest, disease and fertiliser advice from the Upazila Agriculture Officer and the block Sub-Assistant Agriculture Officer (SAAO)",
            "Soil testing referral and fertiliser recommendation for your specific field",
            "The register of LICENSED pesticide and fertiliser dealers in the upazila — ask here to find a legitimate dealer",
            "Complaints about adulterated or overpriced inputs",
            "Information on agricultural machinery subsidy eligibility",
            "Distribution of government seed and fertiliser incentives",
        ],
        "services_bn": [
            "উপজেলা কৃষি অফিসার ও ব্লকের উপসহকারী কৃষি অফিসারের (এসএএও) কাছ থেকে ফসল, পোকা, রোগ ও সার বিষয়ে বিনামূল্যে পরামর্শ",
            "মাটি পরীক্ষার ব্যবস্থা ও আপনার নির্দিষ্ট জমির জন্য সারের সুপারিশ",
            "উপজেলার লাইসেন্সধারী বালাইনাশক ও সার ডিলারের তালিকা — বৈধ দোকান খুঁজতে এখানেই জিজ্ঞাসা করুন",
            "ভেজাল বা বেশি দামে উপকরণ বিক্রির অভিযোগ",
            "কৃষি যন্ত্রপাতি ভর্তুকির যোগ্যতা সম্পর্কে তথ্য",
            "সরকারি বীজ ও সার প্রণোদনা বিতরণ",
        ],
        "brands_stocked": [],
        "opening_hours_en": "Sunday-Thursday, 9:00 am - 5:00 pm (government office hours)",
        "opening_hours_bn": "রবি-বৃহস্পতিবার, সকাল ৯টা - বিকাল ৫টা (সরকারি অফিস সময়)",
        "website": f"https://{url}",
        "source": f"Bangladesh government national portal upazila DAE subdomain pattern (https://{url}); Department of Agricultural Extension",
        "source_type": "official",
        "confidence": "medium",
        "notes": ("Every upazila in Bangladesh has a DAE office. The URL follows the "
                  "standard national portal pattern dae.<upazila>.<district>.gov.bd but "
                  "has NOT been individually fetched and confirmed for each of these 15 "
                  "upazilas — verify each URL resolves before shipping. Phone numbers are "
                  "published on these pages and should be scraped from there rather than guessed."),
    })

# ---- 2. Union Digital Centre / Upazila Parishad ------------------------
for dist, dist_bn, upa, upa_bn, url in PHASE1:
    add({
        "name_en": f"Upazila Parishad and Union Digital Centres, {upa}",
        "name_bn": f"উপজেলা পরিষদ ও ইউনিয়ন ডিজিটাল সেন্টার, {upa_bn}",
        "type": "government_office",
        "phone": None,
        "address_en": f"Upazila Parishad, {upa}, {dist}",
        "address_bn": f"উপজেলা পরিষদ, {upa_bn}, {dist_bn}",
        "district": dist,
        "upazila": upa,
        "rank_in_upazila": 2,
        "rating": None,
        "products_sold": [],
        "services_en": [
            "General government service access point",
            "Union Digital Centres can help a farmer reach agricultural services online",
            "National information service: 333",
        ],
        "services_bn": [
            "সাধারণ সরকারি সেবা পাওয়ার কেন্দ্র",
            "ইউনিয়ন ডিজিটাল সেন্টার থেকে অনলাইনে কৃষি সেবা পেতে সাহায্য পাওয়া যায়",
            "জাতীয় তথ্য সেবা: ৩৩৩",
        ],
        "brands_stocked": [],
        "opening_hours_en": "Sunday-Thursday, 9:00 am - 5:00 pm",
        "opening_hours_bn": "রবি-বৃহস্পতিবার, সকাল ৯টা - বিকাল ৫টা",
        "website": None,
        "source": "Bangladesh national portal (bangladesh.gov.bd) upazila structure; a2i Union Digital Centre programme",
        "source_type": "official",
        "confidence": "medium",
    })

# ---- 3. BADC district presence ----------------------------------------
for dist, dist_bn in sorted({(d, db) for d, db, _, _, _ in PHASE1}):
    add({
        "name_en": f"BADC (Bangladesh Agricultural Development Corporation) district office / seed dealer network, {dist}",
        "name_bn": f"বিএডিসি (বাংলাদেশ কৃষি উন্নয়ন কর্পোরেশন) জেলা অফিস / বীজ ডিলার নেটওয়ার্ক, {dist_bn}",
        "type": "government_supplier",
        "phone": None,
        "address_en": f"BADC district office, {dist}",
        "address_bn": f"বিএডিসি জেলা অফিস, {dist_bn}",
        "district": dist,
        "upazila": None,
        "rank_in_upazila": None,
        "rating": None,
        "products_sold": ["seed", "fertilizer", "irrigation"],
        "services_en": [
            "Certified seed of BRRI, BARI and BINA released varieties — rice, wheat, maize, potato seed tuber, pulses, oilseeds and vegetables",
            "Non-urea fertiliser distribution through the BADC dealer network",
            "Small-scale irrigation equipment and support",
            "BADC seed carries a certification tag; this is the reference point for what a genuine certified seed pack looks like",
        ],
        "services_bn": [
            "ব্রি, বারি ও বিনা উদ্ভাবিত জাতের সার্টিফাইড বীজ — ধান, গম, ভুট্টা, বীজ আলু, ডাল, তেলবীজ ও সবজি",
            "বিএডিসি ডিলার নেটওয়ার্কের মাধ্যমে ইউরিয়া ছাড়া অন্যান্য সার বিতরণ",
            "ছোট পরিসরের সেচ যন্ত্রপাতি ও সহায়তা",
            "বিএডিসি-র বীজে সার্টিফিকেশন ট্যাগ থাকে; আসল সার্টিফাইড বীজের প্যাকেট দেখতে কেমন হয় তার আদর্শ উদাহরণ এটাই",
        ],
        "brands_stocked": ["BADC"],
        "opening_hours_en": "Sunday-Thursday, 9:00 am - 5:00 pm",
        "opening_hours_bn": "রবি-বৃহস্পতিবার, সকাল ৯টা - বিকাল ৫টা",
        "website": "https://badc.gov.bd",
        "source": "Bangladesh Agricultural Development Corporation (badc.gov.bd); BADC district and dealer network",
        "source_type": "official",
        "confidence": "medium",
        "notes": ("BADC operates district offices and an authorised dealer network nationally. "
                  "The specific office address and phone for each district must be taken from "
                  "badc.gov.bd or the district portal before display."),
    })

# ---- 4. National brand distributors ------------------------------------
for name_en, name_bn, products, cats, note in BRANDS:
    add({
        "name_en": name_en,
        "name_bn": name_bn,
        "type": "brand_distributor",
        "phone": None,
        "address_en": "National — head office in Dhaka; products distributed through licensed dealers nationwide",
        "address_bn": "জাতীয় — প্রধান কার্যালয় ঢাকায়; সারাদেশে লাইসেন্সধারী ডিলারের মাধ্যমে পণ্য বিতরণ",
        "district": None,
        "upazila": None,
        "rank_in_upazila": None,
        "rating": None,
        "products_sold": cats,
        "registered_products": products,
        "services_en": [
            "Manufacturer or registration holder for products recommended in AgroScan treatment cards",
            "Ask your local licensed dealer for these brands by ACTIVE INGREDIENT, not only by trade name",
        ],
        "services_bn": [
            "অ্যাগ্রোস্ক্যানের চিকিৎসা কার্ডে সুপারিশ করা পণ্যের প্রস্তুতকারক বা নিবন্ধনধারী",
            "স্থানীয় লাইসেন্সধারী দোকানে শুধু ব্র্যান্ডের নাম নয়, মূল উপাদানের নাম বলে চান",
        ],
        "brands_stocked": products,
        "opening_hours_en": None,
        "opening_hours_bn": None,
        "website": None,
        "source": ("DAE Plant Protection Wing Registered Pesticides List "
                   "(dae.portal.gov.bd) — company names and AP registration numbers"),
        "source_type": "official",
        "confidence": "high",
        "notes": note + " Contact details are NOT included because they were not verified.",
    })

json.dump(recs, open(D + "suppliers.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

from collections import Counter
print("TOTAL supplier records:", len(recs))
print(Counter(r["type"] for r in recs))
print("records with a phone number:", sum(1 for r in recs if r["phone"]))
print("verified:", sum(1 for r in recs if r["verified"]))
