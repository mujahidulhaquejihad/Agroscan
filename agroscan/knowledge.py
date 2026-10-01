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


def advice_for(
    class_name: str,
    lang: str = "bn",
    *,
    land_size: float | None = None,
    land_unit: str = "decimal",
) -> Optional[dict]:
    """Disease card from data/agroscan/diseases/ for a class name like 'Tomato___Late_blight'."""
    try:
        from agroscan.treatment_detail import advice_from_pack

        return advice_from_pack(class_name, lang, land_size=land_size, land_unit=land_unit) or None
    except Exception:
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
    "রোগ", "পাতা", "গাছ", "ফসল",
}
_NAME_STOPWORDS = {"and", "the", "with", "from", "for", "ও", "এবং"}

# App-usage questions only — not "how do I treat X" / "what pesticide to use".
_APP_HOWTO_RE = re.compile(
    r"(how\s+(?:do\s+i\s+|to\s+)?(?:use|start|upload|scan)(?:\s+(?:this|the|agroscan|the\s+app|this\s+app))?"
    r"|how\s+does\s+(?:this|it|the\s+app|agroscan)\s+work"
    r"|কীভাবে\s+(?:ব্যবহার|আপলোড|স্ক্যান)"
    r"|অ্যাপ(?:টি)?\s*(?:কীভাবে|ব্যবহার)"
    r"|(?:upload|scan)\s+(?:a\s+)?(?:photo|leaf|image|picture))",
    re.I,
)

# "which diseases can you help with?" / "potato diseases list" — not a named-disease lookup.
_CATALOG_RE = re.compile(
    r"("
    r"\bki\s*ki\s+rog"
    r"|\bkon\s*kon\s+rog"
    r"|কোন\s*কোন\s*রোগ"
    r"|কী\s*কী\s*রোগ"
    r"|রোগ(?:ের)?\s*(?:তালিকা|লিস্ট|list)"
    r"|\b(?:disease|diseases)\s*(?:list|names?)"
    r"|\blist\s+(?:of\s+)?(?:\w+\s+)?(?:disease|diseases)"
    r"|\bwhich\s+diseases"
    r"|help\s+korte\s+par"
    r"|সাহায্য\s*করতে\s*পার"
    r"|\bwhat can you\b"
    r")",
    re.I,
)


def _is_healthy_rec(rec: dict) -> bool:
    kb = str(rec.get("kb_key") or "").lower()
    cn = str(rec.get("class_name") or "").lower()
    return "healthy" in kb or "healthy" in cn


def wants_catalog(message: str) -> bool:
    msg = (message or "").strip()
    if not msg:
        return False
    if _CATALOG_RE.search(msg):
        return True
    low = msg.lower()
    return bool(
        re.search(r"\b(diseases|রোগ)\b", low)
        and re.search(r"\b(list|all|সব|names?)\b", low)
    )


def _catalog_reply_lang(message: str, lang: str) -> str:
    text = message or ""
    ascii_n = len(re.findall(r"[A-Za-z]", text))
    bn_n = len(re.findall(r"[\u0980-\u09FF]", text))
    if bn_n >= 6:
        return "bn"
    if ascii_n >= 10 and ascii_n > bn_n * 2:
        return "en"
    return lang or "bn"


def pack_catalog_reply(message: str, lang: str) -> Optional[dict]:
    """List verified treatment pages. Qwen cannot see this catalog."""
    if not wants_catalog(message):
        return None
    try:
        from agroscan.bd_data import treatments
    except Exception:
        return None

    lang = _catalog_reply_lang(message, lang)
    bn = (lang or "").startswith("bn")
    msg = (message or "").lower()
    recs = [r for r in treatments() if not _is_healthy_rec(r)]
    if not recs:
        return None

    mentioned = []
    seen_crop = set()
    for rec in recs:
        crop_en = str(rec.get("crop_en") or "").strip()
        crop_bn = str(rec.get("crop_bn") or "").strip()
        key = crop_en.lower() or crop_bn.lower()
        if not key or key in seen_crop:
            continue
        if crop_mentioned(crop_en, msg) or crop_mentioned(crop_bn, msg):
            mentioned.append(key)
            seen_crop.add(key)

    grouped: Dict[str, List[str]] = {}
    crop_label: Dict[str, str] = {}
    for rec in recs:
        crop_en = str(rec.get("crop_en") or "").strip()
        crop_bn = str(rec.get("crop_bn") or "").strip()
        key = crop_en.lower() or crop_bn.lower()
        if not key:
            continue
        if mentioned and key not in mentioned:
            continue
        dis = str(rec.get("disease_bn") if bn else rec.get("disease_en") or rec.get("disease_bn") or "").strip()
        if not dis:
            continue
        grouped.setdefault(key, [])
        if dis not in grouped[key]:
            grouped[key].append(dis)
        crop_label[key] = crop_bn if bn and crop_bn else crop_en or crop_bn

    if not grouped:
        return None

    lines = []
    if mentioned:
        lines.append(
            "এই ফসলের যে রোগগুলোর verified চিকিৎসা পাতা আছে:"
            if bn
            else "I have verified treatment pages for these diseases:"
        )
    else:
        lines.append(
            "আমি এই ফসলগুলোর verified চিকিৎসা পাতায় সাহায্য করতে পারি (নাম বলে জিজ্ঞাসা করুন, অথবা পাতার ছবি দিন):"
            if bn
            else "I can help with these crops (ask by disease name, or upload a leaf photo):"
        )
    for key, names in grouped.items():
        lines.append(f"{crop_label[key]}: " + ", ".join(names))
    n = sum(len(v) for v in grouped.values())
    lines.append(
        f"মোট {n}টি রোগের লেখা আছে। ক্যামেরা আরও ক্লাস চিনতে পারে, কিন্তু চিকিৎসার পাতা শুধু এগুলোর।"
        if bn
        else f"{n} treatment write-ups in total. The camera can flag more classes; only these have a treatment page."
    )
    return {
        "reply": "\n".join(lines),
        "suggestions": _suggestions("bn" if bn else "en"),
        "source": "catalog",
    }


def _split_name(text: str) -> list:
    return [t for t in re.split(r"[\s,./;:()+\-]+", (text or "").strip().lower()) if t]


_YA = "(?:\u09df|\u09af\u09bc)"
# ponytail: fixed Bangla suffix list; add one here if a real inflection ('আমের', 'চায়ের') stops matching.
_BN_CROP_SUFFIX = (
    f"(?:র|ের|এর|{_YA}ের|{_YA}ে|{_YA}|ে|তে|টি|টা|গুলো|গুলোর|গাছ|গাছের|গাছে|পাতা|পাতার|ক্ষেত|ক্ষেতে|বাগান|বাগানে)?"
)


def _word_in(token: str, words: list) -> bool:
    """Disease-name token starts a message word: 'ব্লাস্টে' has 'ব্লাস্ট'; 'protect' does not have 'rot'."""
    return any(w.startswith(token) for w in words)


def crop_mentioned(crop: str, msg: str) -> bool:
    """Whole-word crop match: 'আমের', 'tomatoes' count; 'আমি' (I), 'চাষ' (farming), 'price' do not."""
    crop = (crop or "").strip().lower()
    if len(crop) < 2:
        return False
    if crop.isascii():
        return re.search(rf"\b{re.escape(crop)}(?:e?s)?\b", msg) is not None
    return (
        re.search(rf"(?<![\u0980-\u09ff]){re.escape(crop)}{_BN_CROP_SUFFIX}(?![\u0980-\u09ff])", msg)
        is not None
    )


def _disease_name_tokens(dis_en: str, dis_bn: str, crop_en: str, crop_bn: str) -> list:
    """Tokens that identify the disease, not the crop or generic words.

    Farmer Bangla inflects ('ব্লাস্টে' vs pack 'ব্লাস্ট রোগ'); full-phrase match misses.
    Split on spaces — do not use \\w, which tears Bangla into single consonants.
    """
    crop_bits = _split_name(f"{crop_en} {crop_bn}")
    out = []
    for tok in _split_name(f"{dis_en} {dis_bn}"):
        if len(tok) < 3 or tok in _WEAK_DISEASE_TOKENS or tok in _NAME_STOPWORDS:
            continue
        if tok in crop_bits or any(c and len(c) >= 2 and (c in tok or tok in c) for c in crop_bits):
            continue
        out.append(tok)
    return out


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

    msg_words = _split_name(msg)
    for rec in treatments():
        class_name = str(rec.get("class_name") or "")
        kb = str(rec.get("kb_key") or "")
        crop_en = str(rec.get("crop_en") or "").lower()
        crop_bn = str(rec.get("crop_bn") or "").lower()
        # "Corn_(maize)" -> "corn maize", so "corn" counts as the crop, not a disease word.
        class_crop = class_name.split("___", 1)[0].replace("_", " ").lower()
        dis_en = str(rec.get("disease_en") or "").lower()
        dis_bn = str(rec.get("disease_bn") or "").lower()
        score = 0
        phrase = kb.replace("_", " ")

        if dis_en and dis_en in msg:
            score += 12
        if dis_bn and dis_bn in msg:
            score += 12
        name_toks = _disease_name_tokens(dis_en, dis_bn, f"{crop_en} {class_crop}", crop_bn)
        token_hits = sum(_word_in(t, msg_words) for t in set(name_toks))
        token_hit = token_hits > 0
        if token_hit:
            score += 12 + 6 * (token_hits - 1)  # more name words matched = more specific
        if phrase and phrase in msg:
            score += 10
        crop_hit = crop_mentioned(crop_en, msg) or crop_mentioned(crop_bn, msg)
        if crop_hit:
            score += 8

        tokens = [t for t in kb.split("_") if len(t) > 2 and t not in _WEAK_DISEASE_TOKENS]
        if tokens and all(_word_in(t, msg_words) for t in tokens):
            score += 4 * len(tokens)

        if kb == "late_blight" and "late" in msg and "blight" in msg:
            score = max(score, 11)
        if kb == "early_blight" and "early" in msg and "blight" in msg:
            score = max(score, 11)
        if "northern" in kb and "northern" in msg and "blight" in msg:
            score = max(score, 11)

        disease_hit = bool(
            (dis_en and dis_en in msg)
            or (dis_bn and dis_bn in msg)
            or token_hit
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
    return out or _score_generic_name(msg, lang)


_DISEASE_KINDS = {"blight", "rust", "mold", "spot", "virus"}


def _score_generic_name(msg: str, lang: str) -> List[dict]:
    """'rust', 'leaf blight', 'corn rust': only weak words, so offer every disease named with all of them."""
    from agroscan.bd_data import treatments
    from agroscan.treatment_detail import advice_from_pack

    words = set(_split_name(msg))
    weak = words & _WEAK_DISEASE_TOKENS
    if not weak & _DISEASE_KINDS:
        return []
    hits = []
    for rec in treatments():
        name = set(_split_name(f"{rec.get('disease_en') or ''} {rec.get('disease_bn') or ''}"))
        if not weak <= name:
            continue
        class_crop = str(rec.get("class_name") or "").split("___", 1)[0].replace("_", " ")
        crop = set(_split_name(f"{rec.get('crop_en') or ''} {rec.get('crop_bn') or ''} {class_crop}"))
        hits.append((rec, bool(words & crop)))
    if any(crop_hit for _, crop_hit in hits):
        hits = [h for h in hits if h[1]]
    out: List[dict] = []
    for rec, crop_hit in hits:
        info = advice_from_pack(str(rec.get("class_name")), lang)
        if info:
            out.append(
                {
                    "score": 18 if crop_hit else 8,
                    "info": info,
                    "class_name": rec.get("class_name"),
                    "kb_key": rec.get("kb_key") or "",
                    "crop_hit": crop_hit,
                    "disease_hit": True,
                    "label": _option_label(info, lang),
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

    # How to use the app — not "how do I treat X"
    if msg and _APP_HOWTO_RE.search(message or ""):
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

    catalog = pack_catalog_reply(message, lang)
    if catalog:
        return catalog

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
