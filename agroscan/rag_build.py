"""Build verified RAG disease documents from the Bangladesh data pack.

Source of truth: data/agroscan/disease_treatments.json (DAE/PPW-backed pack).
Does not invent doses, products, or registration numbers — only reformats pack fields
into sectioned documents for retrieval.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agroscan.bd_data import treatments
from agroscan.config import AGROSCAN_PACK_DIR

OUT_NAME = "rag_disease_docs.json"


def _is_healthy(rec: dict) -> bool:
    kb = str(rec.get("kb_key") or "").lower()
    cn = str(rec.get("class_name") or "").lower()
    return kb.startswith("healthy") or "___healthy" in cn or cn.endswith("healthy")


def _lines(items: Any) -> List[str]:
    out: List[str] = []
    if not items:
        return out
    if isinstance(items, str):
        return [items.strip()] if items.strip() else []
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                title = str(it.get("title") or "").strip()
                detail = str(it.get("detail") or "").strip()
                step = it.get("step")
                prefix = f"{step}. " if step is not None else ""
                if title and detail:
                    out.append(f"{prefix}{title}: {detail}")
                elif title:
                    out.append(f"{prefix}{title}")
                elif detail:
                    out.append(f"{prefix}{detail}")
            else:
                s = str(it).strip()
                if s:
                    out.append(s)
    return out


def _chem_block(chem: dict, lang: str) -> str:
    bn = lang.startswith("bn")
    name = (chem.get("product_name_bn") if bn else chem.get("product_name_en")) or chem.get(
        "product_name_en"
    ) or ""
    dose = (chem.get("dose_bn") if bn else chem.get("dose_en")) or chem.get("dose_en") or ""
    how = (
        (chem.get("application_method_bn") if bn else chem.get("application_method_en"))
        or chem.get("application_method_en")
        or ""
    )
    timing = (chem.get("timing_bn") if bn else chem.get("timing_en")) or chem.get("timing_en") or ""
    phi = (
        (chem.get("pre_harvest_interval_note_bn") if bn else chem.get("pre_harvest_interval_note_en"))
        or chem.get("pre_harvest_interval_note_en")
        or ""
    )
    parts = [f"Product: {name}"]
    if chem.get("active_ingredient"):
        parts.append(f"Active ingredient: {chem.get('active_ingredient')}")
    if dose:
        parts.append(f"Dose: {dose}")
    if how:
        parts.append(f"How to apply: {how}")
    if timing:
        parts.append(f"Timing: {timing}")
    if chem.get("interval_days") is not None:
        parts.append(f"Spray interval (days): {chem.get('interval_days')}")
    if chem.get("max_applications_per_season") is not None:
        parts.append(f"Max sprays per season: {chem.get('max_applications_per_season')}")
    if chem.get("phi_days") is not None:
        parts.append(f"PHI (days): {chem.get('phi_days')}")
    if phi:
        parts.append(f"PHI note: {phi}")
    brands = chem.get("brands_available_bd") or []
    if brands:
        parts.append("Brands in BD: " + ", ".join(str(b) for b in brands))
    verified = chem.get("registration_verified")
    if verified is True:
        aps = chem.get("verified_ap_numbers") or []
        ap = (", ".join(str(a) for a in aps)) if aps else "verified"
        parts.append(f"Registration: verified ({ap})")
    elif verified is False:
        parts.append("Registration: not individually verified — confirm AP number with dealer/PPW list")
    ref = chem.get("registration_ref")
    if ref:
        parts.append(f"Registration note: {ref}")
    return "\n".join(parts)


def _pick(rec: dict, en: str, bn: str, lang: str):
    if lang.startswith("bn"):
        return rec.get(bn) or rec.get(en)
    return rec.get(en) or rec.get(bn)


def build_disease_doc(rec: dict, lang: str) -> Optional[Dict[str, Any]]:
    """One verified disease document with overview / symptoms / prevention / treatment / process."""
    if _is_healthy(rec):
        return None
    class_name = str(rec.get("class_name") or "")
    kb_key = str(rec.get("kb_key") or "")
    if not class_name:
        return None

    crop = _pick(rec, "crop_en", "crop_bn", lang) or ""
    disease = _pick(rec, "disease_en", "disease_bn", lang) or ""
    title = f"{crop} — {disease}".strip(" —")
    pathogen = rec.get("pathogen") or ""
    severity = rec.get("severity") or ""
    seasons = ", ".join(str(s) for s in (rec.get("seasons_relevant") or []))
    months = ", ".join(str(m) for m in (rec.get("months_relevant") or []))
    summary = _pick(rec, "summary_en", "summary_bn", lang) or ""
    source = rec.get("source") or ""
    confidence = rec.get("confidence") or ""
    last_verified = rec.get("last_verified") or ""

    symptoms = _lines(_pick(rec, "symptoms_en", "symptoms_bn", lang))
    prevention = _lines(_pick(rec, "cultural_control_en", "cultural_control_bn", lang))
    fertilizer = _pick(rec, "fertilizer_advice_en", "fertilizer_advice_bn", lang) or ""
    organic = _lines(_pick(rec, "organic_alternatives_en", "organic_alternatives_bn", lang))
    process = _lines(_pick(rec, "immediate_actions_en", "immediate_actions_bn", lang))
    outcome = _pick(rec, "expected_outcome_en", "expected_outcome_bn", lang) or ""
    helpline = _pick(rec, "when_to_call_helpline_en", "when_to_call_helpline_bn", lang) or ""
    safety = _pick(rec, "safety_warning_en", "safety_warning_bn", lang) or ""
    legal = _pick(rec, "legal_note_en", "legal_note_bn", lang) or ""
    notes = rec.get("notes") or ""

    chem_blocks = []
    for c in rec.get("chemical_treatments") or []:
        if isinstance(c, dict):
            chem_blocks.append(_chem_block(c, lang))

    overview = "\n".join(
        p
        for p in [
            f"Disease: {title}",
            f"Crop: {crop}",
            f"Pathogen: {pathogen}" if pathogen else "",
            f"Severity: {severity}" if severity else "",
            f"Seasons: {seasons}" if seasons else "",
            f"Months: {months}" if months else "",
            f"Summary: {summary}" if summary else "",
            f"Source: {source}" if source else "",
            f"Confidence: {confidence}" if confidence else "",
            f"Last verified: {last_verified}" if last_verified else "",
            f"Curable with chemicals: {rec.get('is_curable_with_chemicals')}",
        ]
        if p
    )

    symptoms_text = "\n".join(
        [
            f"Symptoms of {title}:",
            *[f"- {s}" for s in symptoms],
        ]
    )

    prevention_text = "\n".join(
        [
            f"Prevention for {title}:",
            *[f"- {s}" for s in prevention],
            (f"Fertilizer advice: {fertilizer}" if fertilizer else ""),
        ]
    ).strip()

    treatment_parts = [
        f"Treatment plan for {title}:",
        "Use only DAE / Plant Protection Wing registered products. Confirm label dose before spraying.",
    ]
    if chem_blocks:
        for i, block in enumerate(chem_blocks, 1):
            treatment_parts.append(f"\nChemical option {i}:\n{block}")
    else:
        treatment_parts.append("No chemical cure listed in the pack for this disease.")
    if organic:
        treatment_parts.append("\nOrganic / non-chemical options:")
        treatment_parts.extend(f"- {s}" for s in organic)
    if safety:
        treatment_parts.append(f"\nSafety: {safety}")
    if legal:
        treatment_parts.append(f"\nLegal: {legal}")
    if notes:
        treatment_parts.append(f"\nPack notes: {notes}")
    treatment_text = "\n".join(treatment_parts)

    process_parts = [
        f"Step-by-step process for {title}:",
        *[f"- {s}" for s in process],
    ]
    if outcome:
        process_parts.append(f"Expected outcome: {outcome}")
    if helpline:
        process_parts.append(f"When to call helpline (16123): {helpline}")
    process_text = "\n".join(process_parts)

    # Full combined doc (also stored for browsing / future use)
    full = "\n\n".join([overview, symptoms_text, prevention_text, treatment_text, process_text])

    return {
        "class_name": class_name,
        "kb_key": kb_key,
        "crop_en": rec.get("crop_en"),
        "crop_bn": rec.get("crop_bn"),
        "disease_en": rec.get("disease_en"),
        "disease_bn": rec.get("disease_bn"),
        "lang": "bn" if lang.startswith("bn") else "en",
        "title": title,
        "confidence": confidence,
        "last_verified": last_verified,
        "source": source,
        "sections": {
            "overview": overview,
            "symptoms": symptoms_text,
            "prevention": prevention_text,
            "treatment": treatment_text,
            "process": process_text,
        },
        "full": full,
    }


def build_all() -> Dict[str, Any]:
    docs: List[dict] = []
    for rec in treatments():
        for lang in ("en", "bn"):
            doc = build_disease_doc(rec, lang)
            if doc:
                docs.append(doc)
    payload = {
        "meta": {
            "source": "disease_treatments.json Bangladesh AgroScan pack",
            "policy": "Verified pack fields only — no invented doses or AP numbers",
            "disease_docs": len(docs) // 2,
            "documents": len(docs),
        },
        "documents": docs,
    }
    out_path = Path(AGROSCAN_PACK_DIR) / OUT_NAME
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(out_path), **payload["meta"]}


if __name__ == "__main__":
    info = build_all()
    print(json.dumps(info, ensure_ascii=False, indent=2))
