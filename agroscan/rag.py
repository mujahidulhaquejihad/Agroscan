"""Lightweight TF-IDF RAG over verified AgroScan disease docs (CPU only).

Primary source: data/agroscan/diseases/*.json, built in memory by rag_build
(sectioned overview / symptoms / prevention / treatment / process).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import List, Optional, Set

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SECTION_ORDER = ("overview", "symptoms", "prevention", "treatment", "process")
# Treatment pages mix 2–3 chemicals + organic + safety. One TF-IDF vector
# buries option 2, and retrieve() used to cut at 2200 chars.
_TREAT_SPLIT = re.compile(
    r"\n(?=Chemical option \d+:|Organic / non-chemical options:|Safety:|Legal:|Pack notes:)"
)


def _section_bodies(section: str, body: str) -> List[str]:
    """Split treatment into chemical / organic pieces; keep safety as one tail.

    Header stays prepended to each product piece so TF-IDF still sees the crop.
    Legal/notes do not compete with dose chunks for the top-k slots.
    """
    body = (body or "").strip()
    if not body:
        return []
    if section != "treatment":
        return [body]
    bits = [p.strip() for p in _TREAT_SPLIT.split(body) if p.strip()]
    if len(bits) <= 1:
        return bits or [body]
    header = ""
    chems: List[str] = []
    organic = ""
    tail: List[str] = []
    for p in bits:
        if p.startswith("Chemical option"):
            chems.append(p)
        elif p.startswith("Organic /"):
            organic = p
        elif p.startswith(("Safety:", "Legal:", "Pack notes:")):
            tail.append(p)
        elif not header:
            header = p
        else:
            tail.append(p)
    prefix = f"{header}\n\n" if header else ""
    out = [f"{prefix}{c}" for c in chems]
    if organic:
        out.append(f"{prefix}{organic}")
    if tail:
        out.append("\n\n".join(tail))
    return out or [body]


def _chunks() -> List[dict]:
    from agroscan.rag_build import build_all

    out: List[dict] = []
    for doc in build_all():
        class_name = str(doc.get("class_name") or "")
        kb_key = str(doc.get("kb_key") or "")
        lang = str(doc.get("lang") or "en")
        title = str(doc.get("title") or "")
        crop_en = str(doc.get("crop_en") or "")
        disease_en = str(doc.get("disease_en") or "")
        crop_bn = str(doc.get("crop_bn") or "")
        disease_bn = str(doc.get("disease_bn") or "")
        aliases = " ".join(
            x for x in (title, crop_en, disease_en, crop_bn, disease_bn, kb_key.replace("_", " "), class_name.replace("___", " ")) if x
        )
        sections = doc.get("sections") or {}
        for section in SECTION_ORDER:
            for i, body in enumerate(_section_bodies(section, str(sections.get(section) or ""))):
                text = f"{aliases}\nSection: {section}\n{body}"
                out.append(
                    {
                        "key": class_name or kb_key,
                        "kb_key": kb_key,
                        "class_name": class_name,
                        "section": section,
                        "piece": i,
                        "lang": lang,
                        "text": text,
                    }
                )
    return out


@lru_cache(maxsize=1)
def _index():
    chunks = _chunks()
    docs = [c["text"] for c in chunks]
    if not docs:
        vectorizer = TfidfVectorizer(max_features=1000)
        matrix = vectorizer.fit_transform(["empty"])
        return [], vectorizer, matrix
    vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(docs)
    return chunks, vectorizer, matrix


def _key_ok(chunk: dict, allow: Set[str]) -> bool:
    if not allow:
        return True
    cn = str(chunk.get("class_name") or "").lower()
    kb = str(chunk.get("kb_key") or "").lower()
    key = str(chunk.get("key") or "").lower()

    # If caller pinned a PlantVillage class_name, require exact class match.
    class_allows = {a for a in allow if "___" in a}
    if class_allows:
        return bool(cn and cn in class_allows)

    candidates = {cn, kb, key}
    if "___" in cn:
        candidates.add(cn.split("___", 1)[1])
    for a in allow:
        al = a.lower()
        if not al:
            continue
        for c in candidates:
            if c and (al == c or al in c or c in al):
                return True
    return False


def _section_boost(query: str, section: str) -> float:
    q = (query or "").lower()
    sec = (section or "").lower()
    if any(w in q for w in ("prevent", "prevention", "cultural", "প্রতিরোধ", "এড়ান")) and sec == "prevention":
        return 0.15
    if any(w in q for w in ("treat", "spray", "dose", "fungicide", "chemical", "চিকিৎসা", "স্প্রে", "ওষুধ")) and sec == "treatment":
        return 0.15
    if any(w in q for w in ("step", "process", "how", "what to do", "ধাপ", "কী করব", "কি করব")) and sec == "process":
        return 0.12
    if any(w in q for w in ("symptom", "sign", "look", "লক্ষণ", "দেখায়")) and sec == "symptoms":
        return 0.12
    return 0.0


def retrieve(
    query: str,
    lang: str = "en",
    k: int = 6,
    extra: Optional[str] = None,
    allow_keys: Optional[set] = None,
) -> List[str]:
    """Return top-k verified guide snippets for an agri question."""
    q = " ".join(p for p in (extra, query) if p).strip()
    if not q:
        return []
    chunks, vectorizer, matrix = _index()
    if not chunks:
        return []
    scores = cosine_similarity(vectorizer.transform([q]), matrix).ravel().astype(float)
    for i, chunk in enumerate(chunks):
        raw = float(scores[i])
        # ponytail: section boost only on chunks that already match; else "spray" ranks every treatment page
        if raw >= 0.04:
            scores[i] = raw + _section_boost(q, chunk.get("section") or "")
        else:
            scores[i] = raw
    prefer = "bn" if (lang or "").lower().startswith("bn") else "en"
    order = np.argsort(scores)[::-1]
    picked: List[str] = []
    seen = set()
    allow = {str(x).lower() for x in (allow_keys or set()) if x}

    floor = 0.08 if not allow else 0.015
    for want_lang in (prefer, None):
        for i in order:
            if scores[i] < floor:
                break
            chunk = chunks[int(i)]
            if want_lang and chunk.get("lang") != want_lang:
                continue
            if not _key_ok(chunk, allow):
                continue
            dedupe = (
                chunk.get("lang"),
                chunk.get("key"),
                chunk.get("section"),
                chunk.get("piece", 0),
            )
            if dedupe in seen:
                continue
            seen.add(dedupe)
            picked.append(chunk.get("text") or "")
            if len(picked) >= k:
                return picked
    return picked
