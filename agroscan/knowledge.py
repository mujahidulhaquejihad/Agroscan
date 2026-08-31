"""Plant-disease knowledge base + a lightweight offline chatbot.

Powers:
  * treatment advice shown under the ensemble "best answer"
  * the /api/chat assistant (rule-based, works without any external LLM)
  * the /api/resources endpoint (emergency vet hotlines + govt links)

The advice is general agronomic guidance for Bangladeshi farmers and is not a
substitute for a qualified plant doctor / veterinarian.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .disease_guides import DISEASE_GUIDES
from .disease_guides_bn import DISEASE_GUIDES_BN
from .knowledge_bn import DISEASE_INFO_BN, SEVERITY_BN

# --------------------------------------------------------------------------- #
# Emergency contacts (Bangladesh) and government resources
# --------------------------------------------------------------------------- #
EMERGENCY_CONTACTS = [
    {
        "name": "Krishi Call Center (Agriculture Helpline)",
        "phone": "16123",
        "hours": "9am - 5pm, Sat-Thu",
        "note": "Free crop & plant disease advice from agriculture officers.",
    },
    {
        "name": "Department of Livestock Services (Vet Helpline)",
        "phone": "16358",
        "hours": "9am - 5pm",
        "note": "Livestock & veterinary emergencies.",
    },
    {
        "name": "National Emergency Service",
        "phone": "999",
        "hours": "24/7",
        "note": "General emergencies.",
    },
]

GOV_LINKS = [
    {
        "name": "Ministry of Agriculture",
        "abbr": "MoA",
        "url": "https://moa.gov.bd",
        "desc": "National policies, notices, subsidies and agricultural schemes.",
        "category": "ministry",
    },
    {
        "name": "Department of Agricultural Extension (DAE)",
        "abbr": "DAE",
        "url": "http://dae.gov.bd",
        "desc": "Field officers, farmer training and crop extension services nationwide.",
        "category": "extension",
    },
    {
        "name": "Bangladesh Agricultural Research Institute (BARI)",
        "abbr": "BARI",
        "url": "http://www.bari.gov.bd",
        "desc": "Crop research, improved varieties and farm technologies.",
        "category": "research",
    },
    {
        "name": "Bangladesh Rice Research Institute (BRRI)",
        "abbr": "BRRI",
        "url": "http://brri.gov.bd",
        "desc": "Rice varieties, cultivation guides and paddy research.",
        "category": "research",
    },
    {
        "name": "Department of Livestock Services (DLS)",
        "abbr": "DLS",
        "url": "http://dls.gov.bd",
        "desc": "Veterinary care, livestock programmes and animal health.",
        "category": "livestock",
    },
    {
        "name": "Bangladesh Agricultural Research Council (BARC)",
        "abbr": "BARC",
        "url": "http://www.barc.gov.bd",
        "desc": "Coordinates agricultural research across Bangladesh.",
        "category": "research",
    },
    {
        "name": "e-Krishi / Krishi Batayon",
        "abbr": "e-Krishi",
        "url": "http://krishi.gov.bd",
        "desc": "Digital portal for crop info, alerts and farmer services.",
        "category": "digital",
    },
    {
        "name": "Bangladesh Agricultural Development Corporation (BADC)",
        "abbr": "BADC",
        "url": "http://badc.gov.bd",
        "desc": "Seeds, fertiliser distribution and irrigation support.",
        "category": "inputs",
    },
]

# --------------------------------------------------------------------------- #
# Disease knowledge base (keyed by a normalized condition slug)
# --------------------------------------------------------------------------- #
DISEASE_INFO: Dict[str, Dict[str, object]] = {
    "healthy": {
        "title": "Healthy leaf",
        "summary": "No disease detected. The leaf looks healthy.",
        "symptoms": ["Uniform green colour", "No spots, mold or wilting"],
        "treatment": ["No treatment needed."],
        "prevention": ["Keep up balanced fertilisation and irrigation.", "Scout the field weekly for early symptoms."],
        "severity": "none",
    },
    "apple_scab": {
        "title": "Apple scab",
        "summary": "Fungal disease (Venturia inaequalis) causing olive-green to black velvety spots.",
        "symptoms": ["Olive-green/black spots on leaves", "Scabby, cracked fruit", "Early leaf drop"],
        "treatment": ["Apply protectant fungicides (e.g., mancozeb) or captan at green-tip and repeat per label.", "Prune to improve air flow."],
        "prevention": ["Rake and destroy fallen leaves", "Plant resistant varieties", "Avoid overhead irrigation"],
        "severity": "moderate",
    },
    "black_rot": {
        "title": "Black rot",
        "summary": "Fungal disease causing leaf spots ('frog-eye') and fruit rot.",
        "symptoms": ["Brown circular leaf spots with purple margins", "Rotting, shrivelled fruit", "Cankers on twigs"],
        "treatment": ["Remove mummified fruit and cankers", "Apply fungicide (captan/mancozeb) from bloom onward"],
        "prevention": ["Sanitation: remove infected wood & fruit", "Improve canopy airflow"],
        "severity": "moderate",
    },
    "rust": {
        "title": "Rust (incl. cedar-apple & common rust)",
        "summary": "Fungal disease producing orange/rusty pustules on leaves.",
        "symptoms": ["Yellow-orange spots on upper leaf", "Rusty pustules underneath", "Premature leaf drop"],
        "treatment": ["Apply fungicide at first sign (e.g., myclobutanil for cedar-apple rust)", "Remove nearby alternate hosts (junipers) where relevant"],
        "prevention": ["Use resistant varieties", "Avoid prolonged leaf wetness"],
        "severity": "moderate",
    },
    "powdery_mildew": {
        "title": "Powdery mildew",
        "summary": "White powdery fungal growth on leaf surfaces.",
        "symptoms": ["White/grey powder on leaves & shoots", "Distorted, stunted growth"],
        "treatment": ["Apply sulfur or potassium-bicarbonate sprays", "Use systemic fungicide for heavy infection"],
        "prevention": ["Improve airflow & sunlight", "Avoid excess nitrogen", "Plant resistant cultivars"],
        "severity": "moderate",
    },
    "gray_leaf_spot": {
        "title": "Gray leaf spot / Cercospora",
        "summary": "Fungal disease of maize causing rectangular grey-brown lesions.",
        "symptoms": ["Long rectangular tan/grey lesions along veins", "Lesions merge and blight the leaf"],
        "treatment": ["Apply foliar fungicide (strobilurin/triazole) at early disease onset"],
        "prevention": ["Rotate crops", "Use resistant hybrids", "Bury crop residue"],
        "severity": "high",
    },
    "northern_leaf_blight": {
        "title": "Northern leaf blight",
        "summary": "Fungal disease of maize with long cigar-shaped grey-green lesions.",
        "symptoms": ["Cigar-shaped tan lesions on leaves", "Blighted leaves reduce yield"],
        "treatment": ["Apply fungicide if disease appears before tasseling"],
        "prevention": ["Resistant hybrids", "Crop rotation", "Residue management"],
        "severity": "high",
    },
    "esca": {
        "title": "Esca (Black Measles) - grape",
        "summary": "Complex trunk disease of grapevine.",
        "symptoms": ["Tiger-stripe interveinal scorch on leaves", "Dark spots on berries", "Sudden vine collapse (apoplexy)"],
        "treatment": ["No reliable cure; remove and re-train affected arms", "Protect pruning wounds"],
        "prevention": ["Prune in dry weather & seal large cuts", "Avoid vine stress"],
        "severity": "high",
    },
    "leaf_blight": {
        "title": "Leaf blight (Isariopsis) - grape",
        "summary": "Fungal leaf-spot disease of grape.",
        "symptoms": ["Irregular dark-brown leaf spots", "Premature defoliation"],
        "treatment": ["Apply mancozeb/copper fungicide on a protective schedule"],
        "prevention": ["Canopy management for airflow", "Remove fallen leaves"],
        "severity": "moderate",
    },
    "citrus_greening": {
        "title": "Citrus greening (Huanglongbing/HLB)",
        "summary": "Serious bacterial disease spread by the citrus psyllid. No cure.",
        "symptoms": ["Blotchy asymmetric leaf yellowing", "Lopsided bitter fruit", "Twig dieback"],
        "treatment": ["No cure - remove and destroy infected trees to protect the orchard", "Control psyllid vectors with insecticide"],
        "prevention": ["Use certified disease-free saplings", "Aggressive psyllid control", "Regular scouting"],
        "severity": "critical",
    },
    "bacterial_spot": {
        "title": "Bacterial spot",
        "summary": "Bacterial disease of tomato/pepper/peach causing water-soaked spots.",
        "symptoms": ["Small water-soaked spots turning brown/black", "Yellow halos", "Fruit lesions"],
        "treatment": ["Apply copper-based bactericides (limited efficacy)", "Remove severely infected plants"],
        "prevention": ["Use disease-free certified seed", "Avoid overhead watering & working when wet", "Rotate crops"],
        "severity": "high",
    },
    "early_blight": {
        "title": "Early blight",
        "summary": "Fungal disease (Alternaria) of tomato/potato with target-like spots.",
        "symptoms": ["Brown spots with concentric rings ('target')", "Yellowing around spots", "Lower leaves first"],
        "treatment": ["Apply chlorothalonil or mancozeb fungicide", "Remove infected lower leaves"],
        "prevention": ["Mulch to stop soil splash", "Crop rotation", "Adequate plant spacing"],
        "severity": "moderate",
    },
    "late_blight": {
        "title": "Late blight",
        "summary": "Aggressive disease (Phytophthora infestans) - can destroy a field fast.",
        "symptoms": ["Large grey-green water-soaked patches", "White mold under leaf in humid weather", "Rapid collapse"],
        "treatment": ["Act immediately: apply fungicide (chlorothalonil/mancozeb; metalaxyl)", "Destroy infected plants away from the field"],
        "prevention": ["Plant resistant varieties & certified seed", "Avoid leaf wetness", "Do not compost infected debris"],
        "severity": "critical",
    },
    "leaf_mold": {
        "title": "Leaf mold - tomato",
        "summary": "Fungal disease favoured by high humidity (common in greenhouses/poly-tunnels).",
        "symptoms": ["Pale-yellow spots on upper leaf", "Olive-green/brown velvety mold underneath"],
        "treatment": ["Improve ventilation & lower humidity", "Apply fungicide if severe"],
        "prevention": ["Space plants, prune for airflow", "Avoid wetting foliage"],
        "severity": "moderate",
    },
    "septoria_leaf_spot": {
        "title": "Septoria leaf spot - tomato",
        "summary": "Fungal disease causing many small circular spots.",
        "symptoms": ["Numerous small spots with dark margins & grey centres", "Tiny black specks in centre", "Starts on lower leaves"],
        "treatment": ["Apply fungicide (chlorothalonil/mancozeb)", "Remove infected leaves"],
        "prevention": ["Mulch, rotate crops", "Avoid overhead irrigation"],
        "severity": "moderate",
    },
    "spider_mites": {
        "title": "Two-spotted spider mites",
        "summary": "Tiny sap-sucking pests (not a disease) that stipple and web leaves.",
        "symptoms": ["Fine yellow stippling/speckling", "Fine webbing under leaves", "Bronzing & leaf drop"],
        "treatment": ["Spray water to dislodge; use miticide or insecticidal soap/neem oil", "Encourage predatory mites"],
        "prevention": ["Avoid drought stress & dust", "Avoid broad-spectrum insecticides that kill predators"],
        "severity": "moderate",
    },
    "target_spot": {
        "title": "Target spot - tomato",
        "summary": "Fungal disease (Corynespora) with target-like lesions on leaves and fruit.",
        "symptoms": ["Brown spots with concentric rings", "Lesions on stems & fruit"],
        "treatment": ["Apply fungicide (chlorothalonil/mancozeb)", "Remove infected debris"],
        "prevention": ["Airflow, rotation, avoid leaf wetness"],
        "severity": "moderate",
    },
    "mosaic_virus": {
        "title": "Tomato mosaic virus",
        "summary": "Viral disease causing mottling and distortion. No chemical cure.",
        "symptoms": ["Mottled light/dark green leaves", "Distorted, fern-like leaves", "Stunted plants"],
        "treatment": ["No cure - remove & destroy infected plants", "Disinfect hands/tools (milk or bleach solution)"],
        "prevention": ["Use resistant varieties & clean seed", "Wash hands; avoid tobacco use near plants", "Control weeds"],
        "severity": "high",
    },
    "yellow_leaf_curl_virus": {
        "title": "Tomato yellow leaf curl virus (TYLCV)",
        "summary": "Viral disease spread by whiteflies. No cure.",
        "symptoms": ["Upward curling, yellow leaf margins", "Stunted bushy growth", "Heavy flower drop"],
        "treatment": ["No cure - remove infected plants", "Control whitefly vectors (insecticide, yellow sticky traps)"],
        "prevention": ["Resistant varieties", "Whitefly nets / reflective mulch", "Early whitefly control"],
        "severity": "critical",
    },
}

# Map keywords found in a class name's condition to a KB key.
_CONDITION_RULES = [
    ("healthy", "healthy"),
    ("scab", "apple_scab"),
    ("black_rot", "black_rot"),
    ("rust", "rust"),
    ("powdery", "powdery_mildew"),
    ("cercospora", "gray_leaf_spot"),
    ("gray_leaf", "gray_leaf_spot"),
    ("northern_leaf_blight", "northern_leaf_blight"),
    ("esca", "esca"),
    # Longer blight names BEFORE generic leaf_blight
    ("early_blight", "early_blight"),
    ("late_blight", "late_blight"),
    ("leaf_blight", "leaf_blight"),
    ("haunglongbing", "citrus_greening"),
    ("greening", "citrus_greening"),
    ("bacterial_spot", "bacterial_spot"),
    ("leaf_mold", "leaf_mold"),
    ("septoria", "septoria_leaf_spot"),
    ("spider_mites", "spider_mites"),
    ("target_spot", "target_spot"),
    ("mosaic", "mosaic_virus"),
    ("yellow_leaf_curl", "yellow_leaf_curl_virus"),
    ("leaf_scorch", "septoria_leaf_spot"),
]


_GUIDE_FIELDS = (
    "description",
    "next_steps",
    "when_to_call_helpline",
    "expected_outcome",
)


def _attach_guide(info: dict, kb_key: str, lang: str = "bn") -> dict:
    """Attach detailed next-step guide (EN, then BN overlay)."""
    out = dict(info)
    guide = DISEASE_GUIDES.get(kb_key) or {}
    for field in _GUIDE_FIELDS:
        if field in guide:
            out[field] = guide[field]
    if lang == "bn":
        bn_guide = DISEASE_GUIDES_BN.get(kb_key) or {}
        for field in _GUIDE_FIELDS:
            if field in bn_guide:
                out[field] = bn_guide[field]
    return out


def _localize_info(info: dict, lang: str = "bn") -> dict:
    """Merge Bengali fields when lang is 'bn'."""
    key = info.get("matched_key")
    out = dict(info)
    if lang == "bn" and key and key in DISEASE_INFO_BN:
        bn = DISEASE_INFO_BN[key]
        for field in ("title", "summary", "symptoms", "treatment", "prevention"):
            if field in bn:
                out[field] = bn[field]
        sev = out.get("severity")
        if sev in SEVERITY_BN:
            out["severity_label"] = SEVERITY_BN[sev]
    if key:
        out = _attach_guide(out, str(key), lang)
    return out


def advice_for_key(
    kb_key: str,
    lang: str = "bn",
    *,
    land_size: float | None = None,
    land_unit: str = "decimal",
) -> Optional[dict]:
    try:
        from agroscan.treatment_detail import advice_from_pack

        pack = advice_from_pack(kb_key, lang, land_size=land_size, land_unit=land_unit)
        if pack:
            return pack
    except Exception:
        pass
    if kb_key not in DISEASE_INFO:
        return None
    info = dict(DISEASE_INFO[kb_key])
    info["matched_key"] = kb_key
    try:
        from agroscan.treatment_detail import treatment_plan_for

        tp = treatment_plan_for(kb_key, lang, land_size=land_size, land_unit=land_unit)
        if tp:
            info["treatment_plan"] = tp
            if tp.get("land"):
                info["land"] = tp["land"]
            if tp.get("land_followups"):
                steps = list(info.get("next_steps") or [])
                steps.extend(tp["land_followups"])
                info["next_steps"] = steps
    except Exception:
        pass
    return _localize_info(info, lang)


def advice_for(
    class_name: str,
    lang: str = "bn",
    *,
    land_size: float | None = None,
    land_unit: str = "decimal",
) -> Optional[dict]:
    """Return KB info for a full class name like 'Tomato___Late_blight'."""
    try:
        from agroscan.treatment_detail import advice_from_pack

        pack = advice_from_pack(class_name, lang, land_size=land_size, land_unit=land_unit)
        if pack:
            return pack
    except Exception:
        pass
    cond = class_name.split("___", 1)[1] if "___" in class_name else class_name
    key = cond.lower()
    for needle, kb_key in _CONDITION_RULES:
        if needle in key:
            return advice_for_key(kb_key, lang, land_size=land_size, land_unit=land_unit)
    return None


def all_diseases(lang: str = "bn") -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    try:
        from agroscan.bd_data import treatments
        from agroscan.treatment_detail import advice_from_pack

        for rec in treatments():
            name = rec.get("class_name") or rec.get("kb_key")
            if not name:
                continue
            info = advice_from_pack(str(name), lang)
            if info:
                out[str(name)] = info
    except Exception:
        pass
    for k in DISEASE_INFO:
        if k not in out:
            info = advice_for_key(k, lang)
            if info:
                out[k] = info
    return out


# --------------------------------------------------------------------------- #
# Rule-based chatbot
# --------------------------------------------------------------------------- #
_BN_EMERGENCY = {
    "16123": ("কৃষি কল সেন্টার (কৃষি হেল্পলাইন)", "সকাল ৯টা - বিকাল ৫টা, শনি-বৃহ"),
    "16358": ("পশুসম্পদ অধিদফতর (পশুচিকিৎসা হেল্পলাইন)", "সকাল ৯টা - বিকাল ৫টা"),
    "999": ("জাতীয় জরুরি সেবা", "২৪/৭"),
}


def _contacts_text(lang: str = "en") -> str:
    if lang == "bn":
        lines = []
        for c in EMERGENCY_CONTACTS:
            bn = _BN_EMERGENCY.get(c["phone"], (c["name"], c["hours"]))
            lines.append(f"- {bn[0]}: {c['phone']} ({bn[1]})")
        return "বাংলাদেশে জরুরি কৃষি/পশুচিকিৎসা হেল্পলাইন:\n" + "\n".join(lines)
    lines = [f"- {c['name']}: {c['phone']} ({c['hours']})" for c in EMERGENCY_CONTACTS]
    return "Here are emergency agriculture/vet hotlines in Bangladesh:\n" + "\n".join(lines)


# Weak tokens that appear in many disease names — never match on these alone.
_WEAK_DISEASE_TOKENS = {
    "leaf", "spot", "blight", "rust", "mold", "virus", "disease", "plant", "crop",
    "common", "black", "brown", "yellow", "green", "gray", "grey",
}


def _format_pack_reply(info: dict, lang: str) -> str:
    bn = (lang or "").startswith("bn")
    title = info.get("title") or ""
    sev = info.get("severity_label") or info.get("severity") or ""
    summary = info.get("summary") or info.get("description") or ""
    lines = [f"{title}" + (f" ({sev})" if sev else ""), summary]
    steps = info.get("next_steps") or []
    if steps:
        lines.append("")
        lines.append("ধাপে ধাপে:" if bn else "Step by step:")
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                title_s = step.get("title") or ""
                detail = step.get("detail") or ""
                lines.append(f"{i}. {title_s}")
                if detail:
                    lines.append(f"   {detail}")
            else:
                lines.append(f"{i}. {step}")
    treatments = info.get("treatment") or []
    if treatments:
        lines.append("")
        lines.append("চিকিৎসা:" if bn else "Treatment:")
        for t in treatments:
            lines.append(f"• {t}")
    prevention = info.get("prevention") or []
    if prevention:
        lines.append("")
        lines.append("প্রতিরোধ:" if bn else "Prevention:")
        for p in prevention:
            lines.append(f"• {p}")
    call = info.get("when_to_call_helpline")
    if call:
        lines.append("")
        lines.append(("হেল্পলাইন: " if bn else "Helpline: ") + str(call))
    return "\n".join(lines).strip()


def _option_label(info: dict, lang: str = "en") -> str:
    title = str(info.get("title") or "").strip()
    if title:
        return title
    cn = str(info.get("class_name") or "")
    return cn.replace("___", " — ").replace("_", " ")


def _score_pack_candidates(msg: str, lang: str) -> List[dict]:
    """Score every pack disease against the user message."""
    out: List[dict] = []
    try:
        from agroscan.bd_data import treatments
        from agroscan.treatment_detail import advice_from_pack
    except Exception:
        return out

    for rec in treatments():
        class_name = str(rec.get("class_name") or "")
        kb = str(rec.get("kb_key") or "")
        crop_en = str(rec.get("crop_en") or "").lower()
        crop_bn = str(rec.get("crop_bn") or "").lower()
        dis_en = str(rec.get("disease_en") or "").lower()
        dis_bn = str(rec.get("disease_bn") or "").lower()
        score = 0
        phrase = kb.replace("_", " ")

        if dis_en and dis_en in msg:
            score += 12
        if dis_bn and dis_bn in msg:
            score += 12
        if phrase and phrase in msg:
            score += 10
        if crop_en and crop_en in msg:
            score += 8
        if crop_bn and crop_bn in msg:
            score += 8

        tokens = [t for t in kb.split("_") if len(t) > 2 and t not in _WEAK_DISEASE_TOKENS]
        if tokens and all(t in msg for t in tokens):
            score += 4 * len(tokens)

        if kb == "late_blight" and "late" in msg and "blight" in msg:
            score = max(score, 11)
        if kb == "early_blight" and "early" in msg and "blight" in msg:
            score = max(score, 11)
        if "northern" in kb and "northern" in msg and "blight" in msg:
            score = max(score, 11)

        crop_hit = bool((crop_en and crop_en in msg) or (crop_bn and crop_bn in msg))
        disease_hit = bool(
            (dis_en and dis_en in msg)
            or (dis_bn and dis_bn in msg)
            or (phrase and phrase in msg)
            or (kb == "late_blight" and "late" in msg and "blight" in msg)
            or (kb == "early_blight" and "early" in msg and "blight" in msg)
            or ("northern" in kb and "northern" in msg)
        )
        if crop_hit and disease_hit:
            score += 10
        elif crop_hit and not disease_hit:
            score = min(score, 3)

        if score < 8:
            continue
        info = advice_from_pack(class_name, lang)
        if not info:
            continue
        label = _option_label(info, lang)
        # Exact / near-exact confirmation of a prior choice
        if class_name.lower() == msg or label.lower() == msg:
            score += 40
        out.append(
            {
                "score": score,
                "info": info,
                "class_name": class_name,
                "kb_key": kb,
                "crop_hit": crop_hit,
                "disease_hit": disease_hit,
                "label": label,
            }
        )
    return out


def _score_kb_candidates(msg: str, lang: str, exclude_classes: set) -> List[dict]:
    out: List[dict] = []
    for key, _raw in DISEASE_INFO.items():
        if key == "healthy":
            continue
        phrase = key.replace("_", " ")
        score = 0
        if phrase in msg:
            score += 10
        info = advice_for_key(key, lang)
        if not info:
            continue
        title = str(info.get("title") or "").lower()
        if title and title in msg:
            score += 9
        tokens = [t for t in key.split("_") if len(t) > 2 and t not in _WEAK_DISEASE_TOKENS]
        if len(tokens) >= 2 and all(t in msg for t in tokens):
            score += 8
        if key == "late_blight" and "late" in msg and "blight" in msg:
            score = max(score, 11)
        if key == "early_blight" and "early" in msg and "blight" in msg:
            score = max(score, 11)
        if key == "northern_leaf_blight" and "northern" in msg and "blight" in msg:
            score = max(score, 11)
        if score < 8:
            continue
        cn = str(info.get("class_name") or key)
        if cn in exclude_classes:
            continue
        label = _option_label(info, lang)
        if cn.lower() == msg or label.lower() == msg:
            score += 40
        out.append(
            {
                "score": score,
                "info": info,
                "class_name": cn,
                "kb_key": key,
                "crop_hit": False,
                "disease_hit": True,
                "label": label,
            }
        )
    return out


def _clarify_payload(candidates: List[dict], lang: str) -> dict:
    bn = (lang or "").startswith("bn")
    # Deduplicate by class_name, keep highest score
    by_cn: Dict[str, dict] = {}
    for c in sorted(candidates, key=lambda x: -x["score"]):
        cn = c["class_name"]
        if cn and cn not in by_cn:
            by_cn[cn] = c
    opts = list(by_cn.values())[:6]
    if bn:
        reply = "একাধিক রোগ মিলেছে। নিচ থেকে একটি বেছে নিন।"
    else:
        reply = "That name matches more than one disease. Choose one below."
    return {
        "status": "clarify",
        "reply": reply,
        "suggestions": [],
        "options": [
            {
                "class_name": c["class_name"],
                "label": c["label"],
                "kb_key": c.get("kb_key"),
                "score": c["score"],
            }
            for c in opts
        ],
    }


def resolve_disease_query(
    message: str,
    lang: str = "bn",
    confirm_class: Optional[str] = None,
) -> dict:
    """Resolve a disease question.

    Returns one of:
      {"status": "matched", "info": <advice dict>}
      {"status": "clarify", "reply", "suggestions", "options"}
      {"status": "none"}
    """
    from agroscan.treatment_detail import advice_from_pack

    lang = lang or "en"
    if confirm_class:
        info = advice_from_pack(str(confirm_class).strip(), lang)
        if info:
            return {"status": "matched", "info": info}

    msg = (message or "").lower().strip()
    if not msg:
        return {"status": "none"}

    # Confirm by exact class_name pasted in the message
    if "___" in msg:
        for token in re.findall(r"[a-z0-9_,.()]+___[a-z0-9_().]+", msg, flags=re.I):
            info = advice_from_pack(token, lang)
            if info:
                return {"status": "matched", "info": info}

    candidates = _score_pack_candidates(msg, lang)
    seen = {c["class_name"] for c in candidates}
    candidates.extend(_score_kb_candidates(msg, lang, seen))

    if not candidates:
        return {"status": "none"}

    candidates.sort(key=lambda x: -x["score"])
    best = candidates[0]

    # User picked a chip / typed the full label — treat as confirmed
    if best["score"] >= 40:
        return {"status": "matched", "info": best["info"]}

    # Close rivals: same disease name on different crops, or near-tied scores
    margin = 8
    close = [c for c in candidates if c["score"] >= best["score"] - 5]
    same_kb = [
        c
        for c in candidates
        if c.get("kb_key") and c["kb_key"] == best.get("kb_key") and c["score"] >= 8
    ]

    needs_confirm = False
    if len(same_kb) > 1 and not best.get("crop_hit"):
        needs_confirm = True
        close = same_kb
    elif len(close) > 1 and (best["score"] - close[1]["score"]) < margin:
        needs_confirm = True

    if needs_confirm:
        return _clarify_payload(close, lang)

    return {"status": "matched", "info": best["info"]}


def resolve_disease_advice(
    message: str,
    lang: str = "bn",
    confirm_class: Optional[str] = None,
) -> Optional[dict]:
    """Strict disease resolver. Returns advice only when uniquely matched."""
    result = resolve_disease_query(message, lang, confirm_class=confirm_class)
    if result.get("status") == "matched":
        return result.get("info")
    return None


def _suggestions(lang: str) -> List[str]:
    if lang == "bn":
        return ["অ্যাপ কীভাবে ব্যবহার করব?", "লেট ব্লাইট চিকিৎসা", "পশুচিকিৎসককে কল", "সরকারি লিংক"]
    return ["How do I use this app?", "Treat late blight", "Call a vet", "Government links"]


def chatbot_reply(
    message: str,
    context_disease: Optional[str] = None,
    lang: str = "bn",
    confirm_class: Optional[str] = None,
) -> dict:
    """Very small intent-router chatbot. Returns {reply, suggestions}."""
    msg = (message or "").lower().strip()
    bn = lang == "bn" or (lang or "").startswith("bn")
    suggestions = _suggestions("bn" if bn else "en")

    if not msg and not confirm_class:
        return {
            "reply": (
                "হাই! আমি এগ্রোস্ক্যান সহকারী। পাতার রোগ, চিকিৎসা বা অ্যাপ ব্যবহার সম্পর্কে জিজ্ঞাসা করুন।"
                if bn
                else "Hi! I'm the AgroScan assistant. Ask me about a plant disease, treatment, or how to use the app."
            ),
            "suggestions": suggestions,
        }

    # Greetings
    if msg and re.search(r"\b(hi|hello|hey|salam|assalam|নমস্কার|হ্যালো|আসসালাম)\b", msg) and not confirm_class:
        return {
            "reply": (
                "হ্যালো! রোগ নির্ণয়ের জন্য পাতার ছবি আপলোড করুন, অথবা রোগ, চিকিৎসা বা জরুরি পশুচিকিৎসা সম্পর্কে জিজ্ঞাসা করুন।"
                if bn
                else "Hello! Upload a leaf photo for diagnosis, or ask me about any disease, treatment, or emergency vet contact."
            ),
            "suggestions": suggestions,
        }

    # Emergency / vet / call
    if msg and re.search(r"\b(emergency|vet|call|hotline|help ?line|doctor|urgent|জরুরি|পশুচিকিৎসক|কল|হেল্পলাইন)\b", msg):
        return {
            "reply": _contacts_text(lang),
            "suggestions": (
                ["লেট ব্লাইট চিকিৎসা", "অ্যাপ কীভাবে ব্যবহার করব?"]
                if bn
                else ["Treat late blight", "How do I use this app?"]
            ),
        }

    # Government links
    if msg and re.search(r"\b(gov|government|link|website|ministry|dae|bari|brri|সরকার|মন্ত্রণালয়|লিংক)\b", msg):
        links = "\n".join(f"- {g['name']}: {g['url']}" for g in GOV_LINKS)
        return {
            "reply": (
                "বাংলাদেশ কৃষির দরকারি সরকারি রিসোর্স:\n" + links
                if bn
                else "Useful Bangladesh agriculture government resources:\n" + links
            ),
            "suggestions": suggestions,
        }

    # How to use
    if msg and re.search(r"\b(how|use|work|start|upload|scan|guide|help|কীভাবে|ব্যবহার|আপলোড|সাহায্য)\b", msg):
        return {
            "reply": (
                "১) একটি পাতার পরিষ্কার ছবি আপলোড বা টেনে আনুন।\n"
                "২) ধাপ ১ এ নিশ্চিত হয় এটি পাতা কিনা।\n"
                "৩) EfficientNet-B3 এআই মডেল দিয়ে পাতার রোগ বিশ্লেষণ করে ফলাফল ও চিকিৎসা পরামর্শ দেখায়।\n"
                "৪) চিকিৎসা পরামর্শ পাবেন; পশুচিকিৎসককে কল বা আমাকে আরও জিজ্ঞাসা করতে পারেন।"
                if bn
                else (
                    "1) Upload or drag a clear photo of a single leaf.\n"
                    "2) Stage 1 checks it really is a leaf.\n"
                    "3) The EfficientNet-B3 AI model analyses the leaf and I show the diagnosis plus treatment advice.\n"
                    "4) You'll get treatment advice, and can call a vet or message me for more help."
                )
            ),
            "suggestions": (
                ["আলুর নাবি ধ্বসা চিকিৎসা", "পশুচিকিৎসককে কল"]
                if bn
                else ["Potato late blight steps", "Call a vet"]
            ),
        }

    # Strict disease lookup — ask to confirm when the name fits more than one crop
    query = resolve_disease_query(message, lang, confirm_class=confirm_class)
    if query.get("status") == "matched":
        pack = query["info"]
        return {
            "reply": _format_pack_reply(pack, lang),
            "suggestions": suggestions,
            "source": "pack",
            "matched_key": pack.get("matched_key"),
            "class_name": pack.get("class_name"),
        }
    if query.get("status") == "clarify":
        return {
            "reply": query["reply"],
            "suggestions": query.get("suggestions") or [],
            "options": query.get("options") or [],
            "source": "clarify",
        }

    # Context fallback only if the user did not name a disease family
    if context_disease and not re.search(
        r"\b(blight|rust|mildew|mosaic|spot|virus|scab|ধ্বসা|মরিচা|ভাইরাস)\b", msg
    ):
        info = advice_for(context_disease, lang)
        if info:
            return {
                "reply": _format_pack_reply(info, lang),
                "suggestions": suggestions,
                "source": "context",
                "class_name": context_disease,
            }

    return {
        "reply": (
            "আমি পাতার রোগ, চিকিৎসা, জরুরি পশুচিকিৎসা ও সরকারি রিসোর্সে সাহায্য করতে পারি। "
            "যেমন জিজ্ঞাসা করুন: 'আলুর নাবি ধ্বসা ধাপে ধাপে' বা 'পশুচিকিৎসককে কল'।"
            if bn
            else (
                "I can help with plant-leaf diseases, treatments, emergency vet contacts and government resources. "
                "Try asking e.g. 'potato late blight step by step' or 'call a vet'."
            )
        ),
        "suggestions": suggestions,
        "source": "kb",
    }
