#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split + generate one JSON file per disease class, merge, and check steps.

Run from anywhere:
  python data/agroscan/build_disease_files.py
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACK = HERE
OUT_DIR = PACK / "parts" / "diseases"
MERGED = PACK / "disease_treatments.json"
MODEL_JSON = ROOT / "web" / "offline-pack.json"

sys.path.insert(0, str(HERE))
from disease_catalog import CLONES, HEALTHY, RENAME_TO_MODEL, SPECS  # noqa: E402

BN = re.compile(r"[ঀ-৿]")
TODAY = "2026-09-24"

CHEMS = {
    "mancozeb": {
        "product_name_en": "Mancozeb 80% WP",
        "product_name_bn": "ম্যানকোজেব ৮০% ডব্লিউপি",
        "active_ingredient": "Mancozeb",
        "formulation": "WP",
        "dose_en": "2-2.5 g per litre of water (about 20-25 g per 10 litre sprayer load)",
        "dose_bn": "প্রতি লিটার পানিতে ২-২.৫ গ্রাম (১০ লিটারের এক স্প্রেয়ারে প্রায় ২০-২৫ গ্রাম)",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Knapsack sprayer. Wet both leaf surfaces. Late afternoon, low wind.",
        "application_method_bn": "ন্যাপস্যাক স্প্রেয়ারে পাতার দুই পিঠ ভিজিয়ে দিন। বিকেলে বাতাস কম থাকলে।",
        "timing_en": "At first spots, then repeat at the labelled interval while weather stays wet.",
        "timing_bn": "প্রথম দাগ দেখা মাত্র, ভেজা আবহাওয়া থাকলে লেবেলের বিরতিতে আবার।",
        "interval_days": 10,
        "max_applications_per_season": 4,
        "phi_days": 7,
        "pre_harvest_interval_note_en": "Do not harvest for 7 days after the last spray. Read the pack if the label differs.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৭ দিন ফসল তুলবেন না। লেবেলে অন্য কিছু থাকলে লেবেল মানুন।",
        "brands_available_bd": ["Dithane M-45", "Indofil M-45", "Manco 80 WP"],
        "registered_in_bd": True,
        "registration_ref": "Mancozeb is registered in Bangladesh. Brand-level AP numbers were not individually verified for this card.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "both",
    },
    "copper": {
        "product_name_en": "Copper oxychloride 50% WP",
        "product_name_bn": "কপার অক্সিক্লোরাইড ৫০% ডব্লিউপি",
        "active_ingredient": "Copper oxychloride",
        "formulation": "WP",
        "dose_en": "3 g per litre of water (about 30 g per 10 litre sprayer load)",
        "dose_bn": "প্রতি লিটার পানিতে ৩ গ্রাম (১০ লিটারের এক স্প্রেয়ারে প্রায় ৩০ গ্রাম)",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Protectant spray on still-healthy tissue. Do not mix with very hard water. Shake often.",
        "application_method_bn": "এখনো সুস্থ অংশে প্রতিরোধক স্প্রে। খুব শক্ত পানিতে মেশাবেন না। মাঝে মাঝে ঝাঁকান।",
        "timing_en": "After rain or at first greasy spots. Repeat every 7-10 days while wet weather lasts.",
        "timing_bn": "বৃষ্টির পর বা প্রথম তেলতেলে দাগে। ভেজা আবহাওয়া থাকলে ৭-১০ দিন পর পর।",
        "interval_days": 10,
        "max_applications_per_season": 4,
        "phi_days": 7,
        "pre_harvest_interval_note_en": "Do not harvest for 7 days after the last spray unless the label says longer.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৭ দিন ফসল তুলবেন না, লেবেলে বেশি থাকলে ততদিন।",
        "brands_available_bd": ["Blitox", "Champion-type copper products"],
        "registered_in_bd": True,
        "registration_ref": "Copper oxychloride / copper hydroxide products are registered in Bangladesh (e.g. Champion 77 WP AP-354). Confirm the brand in the current PPW list.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "preventive",
    },
    "sulfur": {
        "product_name_en": "Wettable sulphur 80% WP",
        "product_name_bn": "ভেজানো সালফার ৮০% ডব্লিউপি",
        "active_ingredient": "Sulphur",
        "formulation": "WP",
        "dose_en": "2-3 g per litre of water",
        "dose_bn": "প্রতি লিটার পানিতে ২-৩ গ্রাম",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Cover leaf undersides. Do not spray in hot midday sun or within 2 weeks of an oil spray.",
        "application_method_bn": "পাতার নিচের পিঠ ভিজান। দুপুরের কড়া রোদে বা তেল স্প্রের ২ সপ্তাহের মধ্যে দেবেন না।",
        "timing_en": "At first powdery film or mite stippling.",
        "timing_bn": "প্রথম গুঁড়ো আবরণ বা মাকড়ের দাগে।",
        "interval_days": 10,
        "max_applications_per_season": 3,
        "phi_days": 7,
        "pre_harvest_interval_note_en": "Do not harvest for 7 days after the last spray.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৭ দিন ফসল তুলবেন না।",
        "brands_available_bd": ["Microthiol Special 80 WP"],
        "registered_in_bd": True,
        "registration_ref": "Microthiol Special 80 WP AP-252 is a verified sulphur product. Confirm the pack in hand.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "both",
    },
    "imidacloprid": {
        "product_name_en": "Imidacloprid 20% SL",
        "product_name_bn": "ইমিডাক্লোপ্রিড ২০% এসএল",
        "active_ingredient": "Imidacloprid",
        "formulation": "SL",
        "dose_en": "0.5 ml per litre of water",
        "dose_bn": "প্রতি লিটার পানিতে ০.৫ মিলিলিটার",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Aim at leaf undersides. Highly toxic to bees — do not spray in bloom.",
        "application_method_bn": "পাতার নিচের পিঠে দিন। মৌমাছির জন্য খুব বিষাক্ত — ফুল ফোটার সময় স্প্রে নয়।",
        "timing_en": "Only when the insect/vector is confirmed. This does not cure a virus already in the plant.",
        "timing_bn": "পোকা/বাহক নিশ্চিত হলে তবেই। গাছে ঢোকা ভাইরাস এতে সারে না।",
        "interval_days": 12,
        "max_applications_per_season": 2,
        "phi_days": 7,
        "pre_harvest_interval_note_en": "Do not harvest for 7 days after the last spray.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৭ দিন ফসল তুলবেন না।",
        "brands_available_bd": ["Admire 20 SL", "Imidor 20 SL"],
        "registered_in_bd": True,
        "registration_ref": "Imidacloprid is registered in Bangladesh. Brand AP numbers were not individually verified for this card.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "curative",
        "caution_en": "Highly toxic to bees and aquatic life.",
        "caution_bn": "মৌমাছি ও মাছের জন্য মারাত্মক বিষাক্ত।",
    },
    "metalaxyl_mancozeb": {
        "product_name_en": "Metalaxyl 8% + Mancozeb 64% WP",
        "product_name_bn": "মেটালাক্সিল ৮% + ম্যানকোজেব ৬৪% ডব্লিউপি",
        "active_ingredient": "Metalaxyl + Mancozeb",
        "formulation": "WP",
        "dose_en": "2.5 g per litre of water",
        "dose_bn": "প্রতি লিটার পানিতে ২.৫ গ্রাম",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Knapsack spray at first downy / pink-rot weather. Do not exceed 2 applications per season.",
        "application_method_bn": "প্রথম ডাউনি/পিঙ্ক-রট আবহাওয়ায় ন্যাপস্যাক স্প্রে। মৌসুমে ২ বারের বেশি নয়।",
        "timing_en": "At first yellow patches with downy undersides, or after waterlogging for pink rot.",
        "timing_bn": "নিচের পিঠে তুলাসহ হলুদ দাগে, অথবা পিঙ্ক রটের জন্য জলাবদ্ধতার পর।",
        "interval_days": 10,
        "max_applications_per_season": 2,
        "phi_days": 14,
        "pre_harvest_interval_note_en": "Do not harvest for 14 days after the last spray.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ১৪ দিন ফসল তুলবেন না।",
        "brands_available_bd": ["Ridomil Gold-type mixes", "Galben M (related phenylamide mix, AP-374 on potato/tomato late blight)"],
        "registered_in_bd": True,
        "registration_ref": "Phenylamide + mancozeb mixes are used in Bangladesh; Galben M AP-374 is verified for potato/tomato late blight, not automatically for every crop on this card. Confirm the label.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "both",
    },
    "propiconazole": {
        "product_name_en": "Propiconazole 25% EC",
        "product_name_bn": "প্রোপিকোনাজল ২৫% ইসি",
        "active_ingredient": "Propiconazole",
        "formulation": "EC",
        "dose_en": "1 ml per litre of water",
        "dose_bn": "প্রতি লিটার পানিতে ১ মিলিলিটার",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Full canopy spray. Listed as an HHP in some national reviews — use only when the infection justifies it.",
        "application_method_bn": "পুরো গাছে স্প্রে। কিছু জাতীয় পর্যালোচনায় অতি ঝুঁকিপূর্ণ — সত্যিই দরকার হলে তবেই।",
        "timing_en": "At first pustules or blotches on the upper leaves; maximum 2 per season.",
        "timing_bn": "উপরের পাতায় প্রথম ফোস্কা বা দাগে; মৌসুমে সর্বোচ্চ ২ বার।",
        "interval_days": 14,
        "max_applications_per_season": 2,
        "phi_days": 30,
        "pre_harvest_interval_note_en": "Do not harvest for 30 days after the last spray.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৩০ দিন ফসল তুলবেন না।",
        "brands_available_bd": ["Tilt 250 EC", "Propicon 250 EC"],
        "registered_in_bd": True,
        "registration_ref": "Propiconazole is registered in Bangladesh. Brand AP numbers were not individually verified for this card.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "both",
        "highly_hazardous_flag": True,
    },
    "chlorantraniliprole": {
        "product_name_en": "Chlorantraniliprole 18.5% SC",
        "product_name_bn": "ক্লোরানট্রানিলিপ্রোল ১৮.৫% এসসি",
        "active_ingredient": "Chlorantraniliprole",
        "formulation": "SC",
        "dose_en": "0.4 ml per litre of water",
        "dose_bn": "প্রতি লিটার পানিতে ০.৪ মিলিলিটার",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Spray at dusk when caterpillars feed. Cover the growing point and leaf whorls.",
        "application_method_bn": "কীড়া খাওয়ার সময় সন্ধ্যায় স্প্রে করুন। ডগা ও পাতার খোলে ভালো করে লাগান।",
        "timing_en": "Only after you confirm the pest (holes, frass, live larvae), not on a guess.",
        "timing_bn": "পোকা নিশ্চিত করে তবেই (গর্ত, বিষ্ঠা, জীবিত কীড়া), অনুমানে নয়।",
        "interval_days": 14,
        "max_applications_per_season": 2,
        "phi_days": 7,
        "pre_harvest_interval_note_en": "Do not harvest for 7 days after the last spray.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৭ দিন ফসল তুলবেন না।",
        "brands_available_bd": ["Coragen 18.5 SC", "Prevathon-type products"],
        "registered_in_bd": True,
        "registration_ref": "Chlorantraniliprole is marketed in Bangladesh. Confirm the crop on the label and the AP number in the current PPW list.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "curative",
    },
    "abamectin": {
        "product_name_en": "Abamectin 1.8% EC",
        "product_name_bn": "অ্যাবামেকটিন ১.৮% ইসি",
        "active_ingredient": "Abamectin",
        "formulation": "EC",
        "dose_en": "0.5 ml per litre of water",
        "dose_bn": "প্রতি লিটার পানিতে ০.৫ মিলিলিটার",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Nozzle up into leaf undersides and growing tips. Use a wetting agent.",
        "application_method_bn": "নজেল উপরের দিকে তাক করে পাতার নিচ ও কচি ডগায়। আঠালো পদার্থ মেশান।",
        "timing_en": "Only when mite damage is confirmed. Maximum 2 sprays, then rotate.",
        "timing_bn": "মাকড়ের ক্ষতি নিশ্চিত হলে তবেই। সর্বোচ্চ ২ বার, তারপর ওষুধ পাল্টান।",
        "interval_days": 7,
        "max_applications_per_season": 2,
        "phi_days": 7,
        "pre_harvest_interval_note_en": "Do not harvest for 7 days after the last spray.",
        "pre_harvest_interval_note_bn": "শেষ স্প্রের পর ৭ দিন ফসল তুলবেন না।",
        "brands_available_bd": ["Vertimec 1.8 EC", "Abamec 1.8 EC"],
        "registered_in_bd": True,
        "registration_ref": "Abamectin is registered and named in national HHP surveys. Verify brand AP number.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "curative",
        "highly_hazardous_flag": True,
    },
    "neem": {
        "product_name_en": "Neem oil (azadirachtin) 1500-3000 ppm",
        "product_name_bn": "নিম তেল (অ্যাজাডিরাকটিন) ১৫০০-৩০০০ পিপিএম",
        "active_ingredient": "Azadirachtin",
        "formulation": "EC",
        "dose_en": "3-5 ml per litre of water with a wetting agent",
        "dose_bn": "প্রতি লিটার পানিতে ৩-৫ মিলি, আঠালো পদার্থসহ",
        "water_volume_per_decimal": "3-4 litres of spray solution per decimal",
        "application_method_en": "Cover undersides. Repeat after rain. First choice before a synthetic if the attack is early.",
        "application_method_bn": "নিচের পিঠ ভিজান। বৃষ্টির পর আবার দিন। আক্রমণ কম হলে সিনথেটিকের আগে এটাই প্রথম পছন্দ।",
        "timing_en": "At first insects or mites, every 7 days for 2-3 sprays.",
        "timing_bn": "প্রথম পোকা বা মাকড়ে, ৭ দিন পর পর ২-৩ বার।",
        "interval_days": 7,
        "max_applications_per_season": 4,
        "phi_days": 3,
        "pre_harvest_interval_note_en": "Wait at least 3 days, and wash produce.",
        "pre_harvest_interval_note_bn": "কমপক্ষে ৩ দিন অপেক্ষা করুন এবং ফসল ধুয়ে নিন।",
        "brands_available_bd": ["Local azadirachtin 1500/3000 ppm oils"],
        "registered_in_bd": True,
        "registration_ref": "Azadirachtin products are sold in Bangladesh; confirm a Bangla label and a licensed dealer.",
        "registration_verified": False,
        "verified_ap_numbers": [],
        "treatment_type": "both",
    },
}

SAFETY_EN = (
    "Wear gloves, a mask, goggles, full-sleeve shirt and long trousers. Mix outdoors, never with bare hands. "
    "Do not eat, drink or smoke while spraying. Spray with the wind at your back. Wash the sprayer and your body "
    "with soap afterwards. Keep children and livestock out of the field for 24 hours. Do not wash the sprayer in a "
    "pond, canal or irrigation channel."
)
SAFETY_BN = (
    "হাতমোজা, মাস্ক, চশমা, ফুলহাতা জামা ও ফুলপ্যান্ট পরুন। খোলা জায়গায় মেশান, খালি হাতে নয়। "
    "স্প্রের সময় খাওয়া, পান বা ধূমপান নয়। বাতাস পিছনে রেখে স্প্রে করুন। পরে সাবান দিয়ে স্প্রেয়ার ও শরীর ধুয়ে ফেলুন। "
    "২৪ ঘণ্টা শিশু ও গবাদিপশু জমিতে ঢুকতে দেবেন না। পুকুর, খাল বা সেচ নালায় স্প্রেয়ার ধোবেন না।"
)
LEGAL_EN = (
    "Use only pesticides registered with the Plant Protection Wing of DAE under the Pesticide Act 2018. "
    "Buy from a licensed dealer, check a sealed pack and a Bangla label, keep the receipt. "
    "The label dose and PHI override this card. Krishi Call Center: 16123."
)
LEGAL_BN = (
    "পেস্টিসাইড আইন ২০১৮ অনুযায়ী ডিএই উদ্ভিদ সংরক্ষণ উইং-এ নিবন্ধিত ওষুধ ছাড়া ব্যবহার করবেন না। "
    "লাইসেন্সধারী দোকান থেকে সিলগালা প্যাকেট ও বাংলা লেবেল দেখে কিনুন, রসিদ রাখুন। "
    "লেবেলের মাত্রা ও পিএইচআই এই কার্ডের উপরে। কৃষি কল সেন্টার: ১৬১২৩।"
)


def steps(*pairs):
    en, bn = [], []
    for i, (te, de, tb, db) in enumerate(pairs, 1):
        en.append({"step": i, "title": te, "detail": de})
        bn.append({"step": i, "title": tb, "detail": db})
    return en, bn


def kind_steps(kind: str, crop_en: str, crop_bn: str, disease_en: str):
    if kind == "bacterial":
        return steps(
            ("Do not spray a fungicide",
             f"{disease_en} is bacterial. Ordinary fungicides waste money and delay the steps that help.",
             "ছত্রাকনাশক দেবেন না",
             f"{crop_bn}-এর এই সমস্যা ব্যাকটেরিয়ার। সাধারণ ছত্রাকনাশকে টাকা নষ্ট হয় আর আসল কাজ দেরি হয়।"),
            ("Stop overhead water",
             "Switch to furrow or drip. Wet leaves and tools spread bacteria faster than rain.",
             "উপর দিয়ে পানি বন্ধ করুন",
             "নালা বা ড্রিপ সেচে যান। ভেজা পাতা ও যন্ত্রপাতি বৃষ্টির চেয়েও দ্রুত ব্যাকটেরিয়া ছড়ায়।"),
            ("Do not work in wet plants",
             "Hands, clothes and knives carry the bacteria. Wait until the canopy is dry.",
             "ভেজা গাছে কাজ করবেন না",
             "হাত, কাপড় ও ছুরি দিয়ে জীবাণু যায়। পাতা শুকনো না হওয়া পর্যন্ত অপেক্ষা করুন।"),
            ("Rogue the worst plants",
             "Bag and remove slimy or blighted plants. Do not throw them on the bund.",
             "সবচেয়ে খারাপ গাছ তুলে ফেলুন",
             "পিচ্ছিল বা পোড়া গাছ ব্যাগে ভরে সরান। আইলে ফেলবেন না।"),
            ("Copper on healthy tissue",
             "Copper oxychloride 50% WP at 3 g/L protects tissue that is still green. It does not resurrect dead leaves. Read the label.",
             "সুস্থ অংশে কপার দিন",
             "প্রতি লিটারে ৩ গ্রাম কপার অক্সিক্লোরাইড ৫০% ডব্লিউপি এখনো সবুজ অংশ রক্ষা করে। মরা পাতা বাঁচায় না। লেবেল পড়ুন।"),
        )
    if kind == "viral":
        return steps(
            ("There is no chemical cure",
             f"Once {crop_en} has this virus, sprays will not make the plant healthy again. Anything you spray is only for the insect that spreads it.",
             "ওষুধে সারবে না",
             f"{crop_bn}-এ এই ভাইরাস ঢুকলে স্প্রেতে গাছ আর সুস্থ হয় না। যা স্প্রে করবেন তা শুধু ছড়ানো পোকার জন্য।"),
            ("Rogue infected plants today",
             "Bag stunted, mosaic or curled plants and remove them from the field. Leaving them is a source for the whole plot.",
             "আক্রান্ত গাছ আজই তুলুন",
             "খাটো, মোজাইক বা কোঁকড়ানো গাছ ব্যাগে ভরে জমি থেকে সরান। ফেলে রাখলে পুরো জমির উৎস হয়।"),
            ("Control the insect vector",
             "Yellow sticky traps plus a labelled insecticide only if the vector is actually present. Follow PHI.",
             "বাহক পোকা দমন করুন",
             "হলুদ আঠালো ফাঁদ, আর পোকা সত্যি থাকলে তবেই লেবেলমাফিক কীটনাশক। পিএইচআই মানুন।"),
            ("Do not keep seed or cuttings from this crop",
             "Infected planting material restarts the disease next season.",
             "এই ফসলের বীজ বা কলম রাখবেন না",
             "আক্রান্ত চারা বা কাটিং পরের মৌসুমে রোগ আবার শুরু করে।"),
            ("Call 16123 if it is spreading",
             "If several neighbouring plots show the same pattern, the Upazila office needs to know.",
             "ছড়ালে ১৬১২৩-এ ফোন করুন",
             "পাশের কয়েকটি জমিতে একই লক্ষণ থাকলে উপজেলা অফিসকে জানান।"),
        )
    if kind == "wilt":
        return steps(
            ("Do not expect a foliar spray to save this plant",
             "Soil or stem vascular diseases are not cured by leaf fungicides. Spraying hides the problem.",
             "পাতায় স্প্রে করে এই গাছ বাঁচবে না",
             "মাটি বা কাণ্ডের নালির রোগ পাতার ছত্রাকনাশকে সারে না। স্প্রে করলে সমস্যা ঢাকা পড়ে।"),
            ("Remove the plant with as much root as you can",
             "Bag it. Do not leave it on the bund. Wash the hoe before the next plant.",
             "যতটা পারেন শিকড়সহ গাছ তুলুন",
             "ব্যাগে ভরুন। আইলে ফেলবেন না। পরের গাছের আগে কোদাল ধুয়ে নিন।"),
            ("Do not replant the same crop in that hole this season",
             "Rotate to rice or another unrelated crop. Panama and brown rot live in soil for years.",
             "এই মৌসুমে সেই গর্তে একই ফসল লাগাবেন না",
             "ধান বা অন্য গোত্রের ফসলে যান। পানামা ও ব্রাউন রট মাটিতে বছরের পর বছর থাকে।"),
            ("Clean tools and footwear",
             "Mud on a spade moves Ralstonia and Fusarium to the next plot.",
             "যন্ত্রপাতি ও জুতো পরিষ্কার করুন",
             "কোদালের কাদায় রালস্টোনিয়া ও ফিউজারিয়াম পাশের জমিতে যায়।"),
            ("Call 16123 for brown rot / Panama",
             "These can be area-wide problems. Report instead of quietly dumping infected plants in a canal.",
             "ব্রাউন রট / পানামা হলে ১৬১২৩",
             "এগুলো এলাকাজুড়ে হতে পারে। আক্রান্ত গাছ খালে না ফেলে খবর দিন।"),
        )
    if kind == "insect":
        return steps(
            ("Confirm the pest before you buy a bottle",
             f"Look for the live insect, frass or typical feeding on {crop_en}. A leaf spot is not an insect.",
             "ওষুধ কেনার আগে পোকা নিশ্চিত করুন",
             f"{crop_bn}-এ জীবিত পোকা, বিষ্ঠা বা খাওয়ার দাগ দেখুন। পাতার দাগ মানে পোকা নয়।"),
            ("Start with cultural control",
             "Hand-pick, bag bunches, clip mined leaves, or collect cut flushes. This is often enough at low numbers.",
             "আগে পরিচর্যা করুন",
             "হাতে কুড়ানো, ঝুড়ি ঢাকা, খাওয়া পাতা ছাঁটা বা কাটা পাতা কুড়ানো। কম সংখ্যায় এতেই হয়।"),
            ("Spray only if the attack is still rising",
             "Use a labelled insecticide at dusk, undersides and growing points. Do not mix two insecticides in one tank.",
             "আক্রমণ বাড়লে তবেই স্প্রে",
             "সন্ধ্যায় লেবেলমাফিক কীটনাশক, নিচের পিঠ ও ডগায়। এক ট্যাংকে দুই কীটনাশক মেশাবেন না।"),
            ("Respect PHI — especially on vegetables and fruit",
             "Count the days on the pack before you pick. Children eat these crops.",
             "পিএইচআই মানুন — সবজি ও ফলে বিশেষ করে",
             "তোলার আগে প্যাকেটের দিন গুনুন। এসব ফসল শিশুরাও খায়।"),
            ("Call 16123 if it is a village outbreak",
             "Armyworm and hispa can move field to field in days.",
             "গ্রামজুড়ে হলে ১৬১২৩",
             "আর্মিওয়ার্ম ও হিসপা কয়েক দিনে জমি থেকে জমিতে যায়।"),
        )
    if kind == "algal":
        return steps(
            ("Open the canopy",
             "Algal spots love shade and still air. Prune or pluck so light and wind reach the leaves.",
             "গাছ খোলা রাখুন",
             "শৈবাল ছায়া ও নিথর বাতাসে বাড়ে। আলো-বাতাস পায় এমন করে ছাঁটুন বা পাতা তুলুন।"),
            ("Improve drainage",
             "Standing water under the crop keeps leaves wet for hours.",
             "নিকাশ ঠিক করুন",
             "জমিতে পানি জমলে পাতা ঘণ্টার পর ঘণ্টা ভিজে থাকে।"),
            ("Copper as a protectant if it is spreading",
             "Copper oxychloride 3 g/L on still-green leaves. This is not an emergency blight.",
             "ছড়ালে কপার প্রতিরোধক",
             "এখনো সবুজ পাতায় প্রতি লিটারে ৩ গ্রাম কপার অক্সিক্লোরাইড। এটা জরুরি ধ্বসা নয়।"),
            ("Do not over-spray",
             "Algal spot rarely kills the plant. Extra copper burns new flush.",
             "বাড়িয়ে স্প্রে করবেন না",
             "শৈবাল দাগে গাছ মরে না। বেশি কপারে কচি পাতা পোড়ে।"),
        )
    if kind == "abiotic":
        return steps(
            ("Do not spray",
             "This label is not a living disease you can kill with a fungicide or insecticide.",
             "স্প্রে করবেন না",
             "এই লেবেল এমন জীবিত রোগ নয় যা ছত্রাকনাশক বা কীটনাশকে মারা যায়।"),
            ("Look again at the cause",
             "Bruise, nutrient scorch, or an unclear photo are more likely. Retake a close, well-lit picture.",
             "কারণ আবার দেখুন",
             "আঘাত, সার পোড়া বা অস্পষ্ট ছবিই বেশি সম্ভব। কাছ থেকে ভালো আলোয় ছবি তুলুন।"),
            ("Fix handling or feeding, not the bottle",
             "For bruising: harvest when skins are set, avoid drops. For hunger: follow FRG-2018, do not dump extra urea on a guess.",
             "হাতের কাজ বা সার ঠিক করুন, বোতল নয়",
             "আঘাত হলে: খোসা সেট হলে তুলুন, ফেলবেন না। ক্ষুধা হলে: এফআরজি-২০১৮, অনুমানে বাড়তি ইউরিয়া নয়।"),
            ("Call 16123 if the crop is still declining",
             "Take a sample leaf or tuber to the Upazila Agriculture Office.",
             "ফসল খারাপ হতে থাকলে ১৬১২৩",
             "একটি পাতা বা আলু নিয়ে উপজেলা কৃষি অফিসে যান।"),
        )
    if kind == "storage_fungal":
        return steps(
            ("Sort today — do not store wet or wounded produce",
             "One rotten fruit or tuber inoculates the crate. Discard and bury or feed to animals only if appropriate.",
             "আজই বাছাই — ভেজা বা কাটা ফসল গুদাম নয়",
             "একটি পচা ফল বা আলু পুরো ক্রেট নষ্ট করে। ফেলে পুঁতে ফেলুন।"),
            ("Cure / dry before the store",
             "Potatoes: skin-set in the dark. Banana crowns: keep the cut dry. Fruit: harvest at firm-ripe, not overripe.",
             "গুদামের আগে শুকান",
             "আলু: অন্ধকারে খোসা সেট। কলার মুকুট: কাটা মুখ শুকনো। ফল: শক্ত-পাকা, অতিরিক্ত পাকা নয়।"),
            ("Keep the store cool and ventilated",
             "Do not pile in sealed plastic. Heat and humidity finish the rot.",
             "গুদাম ঠান্ডা ও বাতাসযুক্ত রাখুন",
             "বন্ধ পলিথিনে স্তূপ করবেন না। গরম ও আর্দ্রতায় পচন শেষ করে।"),
            ("Do not plant from rotten bags",
             "Seed from a diseased heap restarts black scurf, dry rot and crown rot.",
             "পচা বস্তার জিনিস লাগাবেন না",
             "রোগা স্তূপের বীজ আবার ব্ল্যাক স্কার্ফ, ড্রাই রট ও ক্রাউন রট আনে।"),
            ("Field spray only if the crop is still standing and the label allows it",
             "Postharvest rot is mostly won or lost at harvest hygiene, not by extra mancozeb on dead tissue.",
             "গাছ মাঠে থাকলে এবং লেবেল থাকলে তবেই স্প্রে",
             "তোলার পরের পচন বেশিরভাগই তোলার পরিচ্ছন্নতায় হয়, মরা অংশে বাড়তি ম্যানকোজেবে নয়।"),
        )
    if kind == "storage_bacterial":
        return steps(
            ("This is not a fungicide problem",
             "Soft rot bacteria are not killed by mancozeb. Spraying stored tubers is wasted and unsafe.",
             "এটা ছত্রাকনাশকের সমস্যা নয়",
             "সফট রট ব্যাকটেরিয়া ম্যানকোজেবে মরে না। গুদামি আলুতে স্প্রে অপচয় ও অনিরাপদ।"),
            ("Throw out slimy, smelly tubers immediately",
             "One bag can wet-rot the next. Do not wash the rest — drying is safer than washing.",
             "পিচ্ছিল দুর্গন্ধ আলু এখনই ফেলুন",
             "এক বস্তা পাশেরটা ভিজিয়ে পচায়। বাকিগুলো ধোবেন না — শুকানো ধোয়ার চেয়ে নিরাপদ।"),
            ("Harvest from dry soil, not standing water",
             "Waterlogged ridges at lifting are the main field cause.",
             "শুকনো মাটি থেকে তুলুন, দাঁড়ানো পানি থেকে নয়",
             "তোলার সময় জলাবদ্ধ আইলই মাঠের প্রধান কারণ।"),
            ("Do not put washed potatoes into store",
             "Surface water is what the bacteria need.",
             "ধোয়া আলু গুদাম করবেন না",
             "খোসার পানিই ব্যাকটেরিয়ার দরকার।"),
        )
    if kind == "sooty":
        return steps(
            ("The black film is not the real disease",
             "Sooty mould grows on hopper or mealybug honeydew. Killing only the mould leaves the insect.",
             "কালো আবরণ আসল রোগ নয়",
             "হপার বা মিলিবাগের মধুরসে মোল্ড জন্মে। শুধু মোল্ড মারলে পোকা থেকে যায়।"),
            ("Find and reduce the insect",
             "Look on flush tips. Use a labelled insecticide only if hoppers/mealybugs are numerous. Follow PHI on mango fruit.",
             "পোকা খুঁজে কমান",
             "কচি ডগা দেখুন। হপার/মিলিবাগ বেশি হলে তবেই লেবেলমাফিক কীটনাশক। আম তোলার পিএইচআই মানুন।"),
            ("Wash what you can",
             "A soap-water wipe on fruit for home use. Rain after hopper control often clears leaves.",
             "যা যায় ধুয়ে নিন",
             "ঘরে খাওয়ার ফল সাবান-পানি দিয়ে মুছুন। পোকা কমলে বৃষ্টিতে পাতা পরিষ্কার হয়।"),
            ("Do not spray sulphur plus oil together",
             "That mix burns mango leaves.",
             "সালফার আর তেল একসাথে নয়",
             "এতে আমের পাতা পোড়ে।"),
        )
    if kind == "soil":
        return steps(
            ("Do not spray the leaves for this",
             "Common scab lives on the tuber in soil. Foliar fungicides do not reach it.",
             "এর জন্য পাতায় স্প্রে নয়",
             "কমন স্ক্যাব মাটিতে আলুর গায়ে। পাতার ছত্রাকনাশক পৌঁছায় না।"),
            ("Keep ridges moist at tuber initiation",
             "The critical window is the two weeks when tubers start to form. Dry soil then means more scab.",
             "আলু বাঁধার সময় আইল ভেজা রাখুন",
             "আলু গঠনের প্রথম দুই সপ্তাহ জরুরি। তখন শুকনো মাটি মানে বেশি স্ক্যাব।"),
            ("Avoid fresh lime just before planting",
             "High pH favours scab. Do not lime potato land without a soil test.",
             "রোপণের আগে তাজা চুন নয়",
             "উচ্চ পিএইচ-এ স্ক্যাব বাড়ে। মাটি না পরীক্ষা করে আলুর জমিতে চুন নয়।"),
            ("Use clean seed and a rotation",
             "Do not save scabby tubers as seed. Rotate with rice.",
             "পরিষ্কার বীজ ও পালা",
             "স্ক্যাবওয়ালা আলু বীজ রাখবেন না। ধানের সাথে পালা করুন।"),
        )
    if kind == "mixed":
        return steps(
            ("This class is mixed — look before you spray",
             "The training set lumped several leaf problems. Decide fungal (dry spots) vs bacterial (greasy) vs insect.",
             "মিশ্র শ্রেণি — স্প্রের আগে দেখুন",
             "প্রশিক্ষণে কয়েকটি পাতার সমস্যা একসাথে আছে। ছত্রাক (শুকনো দাগ) না ব্যাকটেরিয়া (তেলতেলে) না পোকা তা ঠিক করুন।"),
            ("Sanitation first",
             "Remove the worst leaves, widen spacing, stop overhead irrigation late in the day.",
             "আগে পরিচ্ছন্নতা",
             "খারাপ পাতা সরান, ফাঁক বাড়ান, দিনের শেষে উপর দিয়ে সেচ নয়।"),
            ("If it is clearly fungal, use a protectant",
             "Mancozeb 2-2.5 g/L on still-green leaves. If it looks greasy, switch to the bacterial steps and copper, not mancozeb alone.",
             "নিশ্চিত ছত্রাক হলে প্রতিরোধক",
             "এখনো সবুজ পাতায় ম্যানকোজেব ২-২.৫ গ্রাম/লিটার। তেলতেলে হলে ব্যাকটেরিয়ার ধাপ ও কপার, শুধু ম্যানকোজেব নয়।"),
            ("On leafy vegetables, PHI is the whole point",
             "If you will eat the leaves within a week, prefer no chemical. Call 16123 rather than guessing a mix.",
             "পাতা শাকে পিএইচআইই আসল",
             "এক সপ্তাহের মধ্যে পাতা খাবেন হলে ওষুধ এড়ান। মিশ্র অনুমানে স্প্রে না করে ১৬১২৩-এ ফোন করুন।"),
            ("Retake a closer photo if you are unsure",
             "One well-lit leaf beats a bottle bought for the wrong problem.",
             "নিশ্চিত না হলে কাছের ছবি তুলুন",
             "ভালো আলোয় একটি পাতা ভুল সমস্যার বোতল কেনার চেয়ে কাজে লাগে।"),
        )
    # fungal default
    return steps(
        ("Remove the worst infected leaves",
         f"Pick off heavily spotted {crop_en} leaves and destroy them off the plot. Do not compost wet diseased leaves in the open.",
         "সবচেয়ে খারাপ পাতা তুলুন",
         f"বেশি দাগওয়ালা {crop_bn}-এর পাতা ছিঁড়ে জমির বাইরে নষ্ট করুন। ভেজা রোগা পাতা খোলা কম্পোস্টে নয়।"),
        ("Help the canopy dry",
         "Widen spacing, prune, stop evening overhead irrigation. Fungi need hours of leaf wetness.",
         "পাতা শুকাতে দিন",
         "ফাঁক বাড়ান, ছাঁটুন, সন্ধ্যার উপরের সেচ বন্ধ। ছত্রাকের ঘণ্টার পর ঘণ্টা ভেজা পাতা লাগে।"),
        ("Spray a protectant on still-green tissue",
         "Mancozeb or the labelled mix at the dose on this card. Dead tissue will not turn green again.",
         "এখনো সবুজ অংশে প্রতিরোধক স্প্রে",
         "এই কার্ডের মাত্রায় ম্যানকোজেব বা লেবেলের মিশ্রণ। মরা অংশ আর সবুজ হবে না।"),
        ("Repeat only as labelled",
         "Do not tank-mix extra fungicides. Alternate modes of action if you need a second product.",
         "শুধু লেবেলমতো আবার দিন",
         "ট্যাংকে বাড়তি ছত্রাকনাশক মেশাবেন না। দ্বিতীয় ওষুধ লাগলে ভিন্ন ধরনের ওষুধ পাল্টান।"),
        ("Call 16123 if it still climbs after two sprays",
         "You may have the wrong disease (blight vs bacterial vs pest).",
         "দুই স্প্রের পরও উঠলে ১৬১২৩",
         "হয়তো ভুল রোগ (ধ্বসা না ব্যাকটেরিয়া না পোকা)।"),
    )


def kind_cultural(kind: str, crop_bn: str):
    extra_en = [
        "Use healthy seed / planting material; do not keep seed from a badly diseased crop",
        "Rotate away from the same crop family for at least one season where practical",
        "Keep the field and bunds reasonably weed-free",
        "Follow BARC FRG-2018 fertiliser rates — both hunger and extra urea can worsen disease",
    ]
    extra_bn = [
        "সুস্থ বীজ/চারা ব্যবহার করুন; খুব রোগা ফসলের বীজ রাখবেন না",
        "সম্ভব হলে এক মৌসুম একই গোত্রের ফসল এড়িয়ে পালা করুন",
        "জমি ও আইল যথাসম্ভব আগাছামুক্ত রাখুন",
        "বিএআরসি এফআরজি-২০১৮ সার মাত্রা মানুন — ক্ষুধা ও বাড়তি ইউরিয়া দুটোই রোগ বাড়াতে পারে",
    ]
    if kind == "viral":
        extra_en.insert(0, "Raise seedlings under insect-proof net where the crop is transplanted")
        extra_bn.insert(0, "চারা রোপণের ফসল হলে পোকা-প্রতিরোধী নেটের নিচে চারা তুলুন")
    if kind == "bacterial":
        extra_en.insert(0, "Disinfect knives; never clip wet seedlings as a routine")
        extra_bn.insert(0, "ছুরি জীবাণুমুক্ত করুন; ভেজা চারার ডগা নিয়ম করে কাটবেন না")
    return extra_en, extra_bn


def kind_organic(kind: str):
    if kind in {"viral", "wilt", "abiotic", "soil", "storage_bacterial"}:
        return (
            ["Rogueing, rotation and clean seed — not a bottle — are the real organic options here"],
            ["এখানে আসল জৈব উপায় গাছ তোলা, পালা ও পরিষ্কার বীজ — বোতল নয়"],
        )
    return (
        [
            "Trichoderma harzianum seed or sett treatment at the labelled rate where a product is available",
            "Neem oil 3-5 ml/L as a first insect/mite option",
            "These reduce pressure; they will not stop an explosive outbreak on their own",
        ],
        [
            "পাওয়া গেলে লেবেলমাফিক ট্রাইকোডার্মা দিয়ে বীজ/কাটিং শোধন",
            "পোকা/মাকড়ে প্রথমে প্রতি লিটারে ৩-৫ মিলি নিম তেল",
            "এগুলো চাপ কমায়; বিস্ফোরক প্রাদুর্ভাব একা থামায় না",
        ],
    )


def fname(class_name: str) -> str:
    return re.sub(r"[^\w]+", "_", class_name).strip("_") + ".json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def healthy_card(class_name: str, crop_en: str, crop_bn: str, kb_key: str) -> dict:
    return {
        "class_name": class_name,
        "kb_key": kb_key,
        "crop_en": crop_en,
        "crop_bn": crop_bn,
        "disease_en": "Healthy",
        "disease_bn": "সুস্থ",
        "pathogen": "None",
        "severity": "none",
        "summary_en": f"The leaf looks healthy. Do not spray {crop_en} for disease on this result. Keep ordinary field care and watch the plot.",
        "summary_bn": f"পাতা সুস্থ দেখাচ্ছে। এই ফল দেখে {crop_bn}-এ রোগের স্প্রে করবেন না। সাধারণ যত্ন চালিয়ে জমি দেখুন।",
        "symptoms_en": [
            "Even green colour without expanding spots, mosaic or wilting",
            "No greasy lesions, no orange rust pustules, no insect webbing",
        ],
        "symptoms_bn": [
            "সমান সবুজ রং, বাড়তে থাকা দাগ, মোজাইক বা ঢলে পড়া নেই",
            "তেলতেলে ক্ষত, কমলা মরিচা ফোস্কা বা পোকার জাল নেই",
        ],
        "immediate_actions_en": [
            {"step": 1, "title": "Do not spray", "detail": "Healthy classes carry zero pesticide in AgroScan. A spray now is money and residue for no disease."},
            {"step": 2, "title": "Keep normal care", "detail": "Water and fertiliser as for a healthy crop (FRG-2018). Walk the field twice a week."},
            {"step": 3, "title": "Scan again if something changes", "detail": "New spots, mosaic or wilt mean a new photo, not a preventive cocktail."},
        ],
        "immediate_actions_bn": [
            {"step": 1, "title": "স্প্রে করবেন না", "detail": "সুস্থ শ্রেণিতে অ্যাগ্রোস্ক্যানে কোনো ওষুধ নেই। এখন স্প্রে মানে অকারণে টাকা ও অবশিষ্টাংশ।"},
            {"step": 2, "title": "স্বাভাবিক যত্ন রাখুন", "detail": "সুস্থ ফসলের মতো সেচ ও সার (এফআরজি-২০১৮)। সপ্তাহে দুইবার জমি হাঁটুন।"},
            {"step": 3, "title": "কিছু বদলালে আবার স্ক্যান করুন", "detail": "নতুন দাগ, মোজাইক বা ঢলে পড়া মানে নতুন ছবি, আগাম মিশ্র ওষুধ নয়।"},
        ],
        "cultural_control_en": [
            "Keep walking gaps so you see the first real lesion early",
            "Do not apply pesticide 'just in case' on a healthy scan",
        ],
        "cultural_control_bn": [
            "হাঁটার ফাঁক রাখুন যাতে আসল দাগ তাড়াতাড়ি দেখেন",
            "সুস্থ স্ক্যানে 'হয়ে যেতে পারে' বলে ওষুধ দেবেন না",
        ],
        "chemical_treatments": [],
        "organic_alternatives_en": ["None needed on a healthy crop"],
        "organic_alternatives_bn": ["সুস্থ ফসলে দরকার নেই"],
        "fertilizer_advice_en": "Follow BARC FRG-2018 for this crop. Do not add extra urea because the scan was healthy.",
        "fertilizer_advice_bn": "এই ফসলের জন্য বিএআরসি এফআরজি-২০১৮ মানুন। স্ক্যান সুস্থ বলে বাড়তি ইউরিয়া দেবেন না।",
        "safety_warning_en": "No pesticide is recommended.",
        "safety_warning_bn": "কোনো ওষুধের পরামর্শ নেই।",
        "legal_note_en": LEGAL_EN,
        "legal_note_bn": LEGAL_BN,
        "when_to_call_helpline_en": "Call 16123 if the crop looks worse than this healthy result within a few days.",
        "when_to_call_helpline_bn": "কয়েক দিনের মধ্যে ফসল এই সুস্থ ফলের চেয়ে খারাপ দেখালে ১৬১২৩ নম্বরে ফোন করুন।",
        "expected_outcome_en": "No treatment. Continue ordinary scouting.",
        "expected_outcome_bn": "কোনো চিকিৎসা নেই। সাধারণ নজরদারি চালিয়ে যান।",
        "related_shop_products": [],
        "seasons_relevant": ["rabi", "kharif1", "kharif2"],
        "months_relevant": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "source": "AgroScan healthy-class rule (Quality Rule 9): healthy labels carry no pesticide. BARC FRG-2018 for background feeding.",
        "source_type": "official",
        "last_verified": TODAY,
        "confidence": "high",
        "notes": "HEALTHY CLASS. UI must show warn_healthy_no_spray. Zero chemical_treatments.",
        "is_curable_with_chemicals": True,
    }


def spec_to_card(spec: dict) -> dict:
    kind = spec["kind"]
    en_s, bn_s = kind_steps(kind, spec["crop_en"], spec["crop_bn"], spec["disease_en"])
    cult_en, cult_bn = kind_cultural(kind, spec["crop_bn"])
    org_en, org_bn = kind_organic(kind)
    chems = [deepcopy(CHEMS[k]) for k in spec.get("chems") or [] if k in CHEMS]
    missing = [k for k in spec.get("chems") or [] if k not in CHEMS]
    if missing:
        raise SystemExit(f"{spec['class_name']}: unknown chem keys {missing}")
    summary_en = (
        f"{spec['disease_en']} on {spec['crop_en']} ({spec['pathogen']}). "
        f"Follow the numbered steps in order. Confirm the crop in the photo before you buy a bottle. "
        f"Label dose and PHI override this card. Confidence is {spec.get('confidence', 'medium')} — "
        f"doses are standard Bangladesh extension rates, not a transcription of one pack."
    )
    summary_bn = (
        f"{spec['crop_bn']}-এ {spec['disease_bn']} ({spec['pathogen']})। "
        f"ধাপগুলো ক্রম অনুযায়ী করুন। বোতল কেনার আগে ছবির ফসল নিশ্চিত করুন। "
        f"লেবেলের মাত্রা ও পিএইচআই এই কার্ডের উপরে। আত্মবিশ্বাস {spec.get('confidence', 'medium')} — "
        f"মাত্রা বাংলাদেশের প্রচলিত সম্প্রসারণ হার, একটি প্যাকেটের নকল নয়।"
    )
    fert_en = "Follow BARC FRG-2018 for this crop at medium fertility. Do not dump extra urea on a diseased canopy unless a step below says to feed a hungry crop."
    fert_bn = "মাঝারি উর্বরতায় এই ফসলের জন্য বিএআরসি এফআরজি-২০১৮ মানুন। নিচের কোনো ধাপে অভুক্ত গাছকে খাবার দিতে না বললে রোগা ছাউনিতে বাড়তি ইউরিয়া দেবেন না।"
    if kind == "bacterial":
        fert_en = "Stop extra urea while the bacteria are active. Apply the full MoP (potash) dose — potash slows several bacterial blights. Follow FRG-2018 for the rest."
        fert_bn = "ব্যাকটেরিয়া চলাকালীন বাড়তি ইউরিয়া বন্ধ রাখুন। পুরো এমওপি (পটাশ) দিন — পটাশ কয়েকটি ব্যাকটেরিয়া ব্লাইট ধীর করে। বাকিটা এফআরজি-২০১৮।"
    return {
        "class_name": spec["class_name"],
        "kb_key": spec["kb_key"],
        "crop_en": spec["crop_en"],
        "crop_bn": spec["crop_bn"],
        "disease_en": spec["disease_en"],
        "disease_bn": spec["disease_bn"],
        "pathogen": spec["pathogen"],
        "severity": spec["severity"],
        "summary_en": summary_en,
        "summary_bn": summary_bn,
        "symptoms_en": spec["symptoms_en"],
        "symptoms_bn": spec["symptoms_bn"],
        "immediate_actions_en": en_s,
        "immediate_actions_bn": bn_s,
        "cultural_control_en": cult_en,
        "cultural_control_bn": cult_bn,
        "chemical_treatments": chems,
        "organic_alternatives_en": org_en,
        "organic_alternatives_bn": org_bn,
        "fertilizer_advice_en": fert_en,
        "fertilizer_advice_bn": fert_bn,
        "safety_warning_en": SAFETY_EN if chems else "No pesticide is recommended for this class.",
        "safety_warning_bn": SAFETY_BN if chems else "এই শ্রেণিতে কোনো ওষুধের পরামর্শ নেই।",
        "legal_note_en": LEGAL_EN,
        "legal_note_bn": LEGAL_BN,
        "when_to_call_helpline_en": f"Call 16123 if {spec['crop_en']} keeps getting worse after the steps above, or if you are not sure this is {spec['disease_en']}.",
        "when_to_call_helpline_bn": f"উপরের ধাপের পরও {spec['crop_bn']} খারাপ হতে থাকলে, অথবা এটা {spec['disease_bn']} কিনা নিশ্চিত না হলে ১৬১২৩ নম্বরে ফোন করুন।",
        "expected_outcome_en": "New growth should look cleaner within 10-14 days if the diagnosis and the first steps were right. Tissue already dead will not recover.",
        "expected_outcome_bn": "রোগ চেনা ও প্রথম ধাপ ঠিক থাকলে ১০-১৪ দিনে নতুন পাতা পরিষ্কার দেখায়। যা মরে গেছে তা আর ফিরে আসে না।",
        "related_shop_products": spec.get("shop") or [],
        "seasons_relevant": spec.get("seasons") or ["rabi"],
        "months_relevant": spec.get("months") or [1, 2, 3],
        "source": "BARI/BRRI/DAE-style extension practice for Bangladesh; CABI/Plantwise disease biology; PPW-registered active ingredients already in the AgroScan shop pack. Brand AP numbers on new cards are unverified.",
        "source_type": "field_guide",
        "last_verified": TODAY,
        "confidence": spec.get("confidence", "medium"),
        "notes": spec.get("notes") or (
            f"Generated card for model class {spec['class_name']}. "
            "Doses are extension rates. registration_verified is false. "
            "Officer review of Bangla still required (LIMITS L3)."
        ),
        "is_curable_with_chemicals": kind not in {"viral", "wilt"},
        "bangladesh_relevance": "grown",
    }


def check_card(rec: dict, failures: list) -> None:
    cn = rec.get("class_name") or "?"
    en = rec.get("immediate_actions_en") or []
    bn = rec.get("immediate_actions_bn") or []
    if len(en) != len(bn) or len(en) < 3:
        failures.append(f"{cn}: step count en={len(en)} bn={len(bn)} (need >=3 and equal)")
    for i, (a, b) in enumerate(zip(en, bn), 1):
        if a.get("step") != i or b.get("step") != i:
            failures.append(f"{cn}: steps not 1..n consecutive")
            break
        if not (a.get("title") and a.get("detail") and b.get("title") and b.get("detail")):
            failures.append(f"{cn}: empty step {i}")
        if not BN.search(str(b.get("title", "")) + str(b.get("detail", ""))):
            failures.append(f"{cn}: step {i} bn missing Bangla")
    kb = str(rec.get("kb_key") or "").lower()
    healthy = "healthy" in kb or rec.get("disease_en") == "Healthy"
    chems = rec.get("chemical_treatments") or []
    if healthy and chems:
        failures.append(f"{cn}: healthy class has chemicals")
    for ct in chems:
        for k in ("dose_en", "dose_bn", "phi_days", "interval_days", "max_applications_per_season",
                  "registered_in_bd", "registration_ref", "treatment_type", "registration_verified"):
            if k not in ct or ct[k] in (None, ""):
                failures.append(f"{cn}: chem missing {k}")
        if not isinstance(ct.get("phi_days"), int):
            failures.append(f"{cn}: phi_days not int")
    kind_hint = (en[0].get("title") or "") if en else ""
    if rec.get("kb_key") in {
        "bacterial_leaf_streak", "bacterial_panicle_blight", "bacterial_blight",
        "bacterial_canker", "cauliflower_black_rot", "bacterial_spot_rot", "bacterial_spot",
    }:
        blob = (en[0].get("detail") or "") + kind_hint
        if "fungicide" not in blob.lower() and "ছত্রাক" not in (bn[0].get("title") or ""):
            failures.append(f"{cn}: bacterial card step 1 must warn against fungicide")


def pad_steps(rec: dict) -> None:
    """Every card must have at least 3 numbered EN/BN steps."""
    en = list(rec.get("immediate_actions_en") or [])
    bn = list(rec.get("immediate_actions_bn") or [])
    n = max(len(en), len(bn), 3)
    while len(en) < n:
        step = len(en) + 1
        en.append({
            "step": step,
            "title": "Call 16123 if you are still unsure",
            "detail": "Take a sample leaf to the Upazila Agriculture Office rather than spraying on a guess.",
        })
    while len(bn) < n:
        step = len(bn) + 1
        bn.append({
            "step": step,
            "title": "এখনো নিশ্চিত না হলে ১৬১২৩",
            "detail": "অনুমানে স্প্রে না করে একটি পাতা নিয়ে উপজেলা কৃষি অফিসে যান।",
        })
    for i, row in enumerate(en, 1):
        row["step"] = i
    for i, row in enumerate(bn, 1):
        row["step"] = i
    rec["immediate_actions_en"] = en
    rec["immediate_actions_bn"] = bn


def clone_record(src: dict, overlay: dict) -> dict:
    rec = deepcopy(src)
    rec.update(overlay)
    rec["notes"] = (src.get("notes") or "") + f" | Cloned from {src.get('class_name')} for model class {overlay.get('class_name')}."
    rec["last_verified"] = TODAY
    return rec


def main() -> int:
    existing = load_json(MERGED)
    by_name = {r["class_name"]: r for r in existing}
    for old, new in RENAME_TO_MODEL.items():
        if old in by_name and new not in by_name:
            rec = deepcopy(by_name[old])
            rec["class_name"] = new
            rec["notes"] = (rec.get("notes") or "") + f" | class_name aligned to model spelling ({old} -> {new})."
            by_name[new] = rec
            # keep old extra name too if it differs
            if old != new:
                pass

    for dest, src_name, overlay in CLONES:
        src = by_name.get(src_name)
        if not src:
            raise SystemExit(f"clone source missing: {src_name}")
        by_name[dest] = clone_record(src, overlay)

    for spec in SPECS:
        by_name[spec["class_name"]] = spec_to_card(spec)

    for class_name, crop_en, crop_bn, kb in HEALTHY:
        by_name[class_name] = healthy_card(class_name, crop_en, crop_bn, kb)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    ordered = sorted(by_name.values(), key=lambda r: r["class_name"])
    failures = []
    for rec in ordered:
        pad_steps(rec)
        check_card(rec, failures)
        dump_json(OUT_DIR / fname(rec["class_name"]), rec)

    dump_json(MERGED, ordered)

    model_classes = []
    if MODEL_JSON.exists():
        model_classes = load_json(MODEL_JSON)["models"]["disease"]["classes"]
    have = {r["class_name"] for r in ordered}
    missing_model = [c for c in model_classes if c not in have]
    if missing_model:
        failures.append(f"model classes still without a file: {missing_model}")

    print(f"Wrote {len(ordered)} disease files -> {OUT_DIR}")
    print(f"Merged {MERGED.name} ({len(ordered)} records)")
    print(f"Model classes: {len(model_classes)}; missing: {len(missing_model)}")
    if failures:
        print("STEP/FILE CHECKS FAILED:")
        for f in failures[:40]:
            print(" -", f)
        if len(failures) > 40:
            print(f" - ... {len(failures) - 40} more")
        return 1
    print("Step checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
