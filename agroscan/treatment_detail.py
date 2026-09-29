"""Detailed treatment plans from the Bangladesh data pack (+ land-size scaling)."""
from __future__ import annotations

from typing import Dict, List, Optional

from agroscan.bd_data import find_treatment, warning_box
from agroscan.land_scale import (
    followup_steps,
    land_summary,
    scale_chemical,
    scale_fertilizer_note,
    to_decimals,
)

GUARD_RELEVANCE = {"not_grown", "not_grown_commercially", "rare_experimental"}
VIRUS_KEYS = {
    "tylcv", "tomato_mosaic_virus", "tungro", "citrus_greening", "chilli_leaf_curl",
    "golden_mosaic", "papaya_mosaic", "papaya_ringspot", "papaya_curl",
    "sugarcane_mosaic", "sugarcane_yellow",
}
BACTERIAL_KEYS = {
    "bacterial_leaf_blight", "bacterial_wilt", "bacterial_spot", "peach_bacterial_spot",
    "bacterial_leaf_streak", "bacterial_panicle_blight", "bacterial_blight",
    "bacterial_canker", "cauliflower_black_rot", "bacterial_spot_rot",
    "potato_brown_rot", "potato_blackleg",
}
HEALTHY_PREFIX = "healthy"


def _pick(row: dict, en_key: str, bn_key: str, lang: str):
    if (lang or "en").startswith("bn"):
        return row.get(bn_key) or row.get(en_key)
    return row.get(en_key) or row.get(bn_key)


def _warnings_for(rec: dict, lang: str) -> List[dict]:
    kb = str(rec.get("kb_key") or "")
    chems = rec.get("chemical_treatments") or []
    out: List[dict] = []
    relevance = rec.get("bangladesh_relevance") or ""
    if relevance in GUARD_RELEVANCE:
        w = warning_box("warn_low_confidence_crop", lang)
        if w:
            out.append(w)
    if kb.startswith(HEALTHY_PREFIX) or not chems:
        if kb.startswith(HEALTHY_PREFIX):
            w = warning_box("warn_healthy_no_spray", lang)
            if w:
                out.append(w)
    if rec.get("is_curable_with_chemicals") is False or kb in VIRUS_KEYS:
        w = warning_box("warn_no_cure_virus", lang)
        if w:
            out.append(w)
        notice = _pick(rec, "no_cure_notice_en", "no_cure_notice_bn", lang)
        if notice:
            out.append({"id": "no_cure_notice", "level": "high", "title": "", "body": notice})
    if kb in BACTERIAL_KEYS:
        w = warning_box("warn_bacterial_not_fungal", lang)
        if w:
            out.append(w)
    if chems:
        w = warning_box("warn_generic_pesticide", lang)
        if w:
            out.append(w)
        w = warning_box("warn_check_label", lang)
        if w:
            out.append(w)
        w = warning_box("warn_fish_safety", lang)
        if w:
            out.append(w)
        w = warning_box("warn_bee_safety", lang)
        if w:
            out.append(w)
        phis = [c.get("phi_days") for c in chems if isinstance(c, dict) and c.get("phi_days") is not None]
        if phis:
            w = warning_box("warn_phi", lang, phi_days=max(int(p) for p in phis))
            if w:
                out.append(w)
        if any(isinstance(c, dict) and c.get("registration_verified") is False for c in chems):
            w = warning_box("warn_registration_unverified", lang)
            if w:
                out.append(w)
        if any(isinstance(c, dict) and c.get("highly_hazardous_flag") for c in chems):
            w = warning_box("warn_hhp", lang)
            if w:
                out.append(w)
    poison = warning_box("warn_poisoning_emergency", lang)
    if poison:
        out.append(poison)
    return out


def _chem_display(
    ct: dict,
    lang: str,
    *,
    decimals: float = 0.0,
) -> dict:
    item = dict(ct)
    item["product"] = _pick(ct, "product_name_en", "product_name_bn", lang)
    item["how_to_apply"] = _pick(ct, "application_method_en", "application_method_bn", lang)
    item["dose_display"] = _pick(ct, "dose_en", "dose_bn", lang)
    item["timing"] = _pick(ct, "timing_en", "timing_bn", lang)
    item["phi_note"] = _pick(ct, "pre_harvest_interval_note_en", "pre_harvest_interval_note_bn", lang)
    item["max_sprays_per_season"] = ct.get("max_applications_per_season")
    item["water_volume_per_decimal"] = ct.get("water_volume_per_decimal")
    verified = bool(ct.get("registration_verified"))
    item["registration_verified"] = verified
    if verified:
        item["ap_numbers"] = ct.get("verified_ap_numbers") or []
        item["registration_ref"] = ct.get("registration_ref")
    else:
        item["ap_numbers"] = []
        item["registration_ref"] = None
    if decimals > 0:
        scaled = scale_chemical(ct, decimals, lang)
        item.update(scaled)
        if scaled.get("dose_scaled"):
            item["dose_display_scaled"] = scaled["dose_scaled"]
    return item


def treatment_plan_for(
    kb_key: str,
    lang: str = "bn",
    *,
    land_size: float | None = None,
    land_unit: str = "decimal",
) -> Optional[dict]:
    rec = find_treatment(kb_key=kb_key)
    if not rec:
        return None
    return _plan_from_record(rec, lang, land_size=land_size, land_unit=land_unit)


def _plan_from_record(
    rec: dict,
    lang: str,
    *,
    land_size: float | None = None,
    land_unit: str = "decimal",
) -> dict:
    decimals = to_decimals(land_size, land_unit) if land_size is not None else 0.0
    chems = [
        _chem_display(c, lang, decimals=decimals)
        for c in (rec.get("chemical_treatments") or [])
        if isinstance(c, dict)
    ]
    fert = _pick(rec, "fertilizer_advice_en", "fertilizer_advice_bn", lang)
    fert_scaled = scale_fertilizer_note(str(fert or ""), decimals, lang) if fert else None
    plan = {
        "matched_key": rec.get("kb_key"),
        "class_name": rec.get("class_name"),
        "chemical_treatments": chems,
        "organic_alternatives": _pick(rec, "organic_alternatives_en", "organic_alternatives_bn", lang) or [],
        "fertilizer_advice": fert,
        "fertilizer_advice_scaled": fert_scaled,
        "safety_warning": _pick(rec, "safety_warning_en", "safety_warning_bn", lang),
        "legal_note": _pick(rec, "legal_note_en", "legal_note_bn", lang),
        "related_shop_skus": rec.get("related_shop_skus") or [],
        "is_curable_with_chemicals": rec.get("is_curable_with_chemicals"),
        "bangladesh_relevance": rec.get("bangladesh_relevance"),
        "warnings": _warnings_for(rec, lang),
        "land_followups": followup_steps(decimals, lang) if decimals > 0 else [],
    }
    if land_size is not None and decimals > 0:
        plan["land"] = {
            "size": land_size,
            "unit": land_unit or "decimal",
            "decimals": round(decimals, 2),
            "summary": land_summary(decimals, float(land_size), land_unit or "decimal", lang),
        }
    return plan


def advice_from_pack(
    class_name: str,
    lang: str = "bn",
    *,
    land_size: float | None = None,
    land_unit: str = "decimal",
) -> Optional[dict]:
    rec = find_treatment(class_name=class_name)
    if not rec and "___" in class_name:
        rec = find_treatment(kb_key=class_name.split("___", 1)[1].lower())
    if not rec:
        rec = find_treatment(kb_key=class_name.lower())
    if not rec:
        return None

    steps_src = rec.get("immediate_actions_bn" if lang.startswith("bn") else "immediate_actions_en")
    if not steps_src:
        steps_src = rec.get("immediate_actions_en") or []
    next_steps = [{"title": s.get("title"), "detail": s.get("detail")} for s in steps_src if isinstance(s, dict)]

    decimals = to_decimals(land_size, land_unit) if land_size is not None else 0.0
    if decimals > 0:
        next_steps = list(next_steps) + followup_steps(decimals, lang)

    chems = rec.get("chemical_treatments") or []
    treatment_bullets = []
    for c in chems:
        if not isinstance(c, dict):
            continue
        name = _pick(c, "product_name_en", "product_name_bn", lang)
        dose = _pick(c, "dose_en", "dose_bn", lang)
        timing = _pick(c, "timing_en", "timing_bn", lang)
        line = name or ""
        if dose:
            line += f" — {dose}"
        if timing:
            line += f". {timing}"
        if decimals > 0:
            scaled = scale_chemical(c, decimals, lang)
            if scaled.get("dose_scaled"):
                line += f" | {scaled['dose_scaled']}"
        if line:
            treatment_bullets.append(line)

    prevention = _pick(rec, "cultural_control_en", "cultural_control_bn", lang) or []
    plan = _plan_from_record(rec, lang, land_size=land_size, land_unit=land_unit)

    out = {
        "title": f"{_pick(rec, 'crop_en', 'crop_bn', lang)} — {_pick(rec, 'disease_en', 'disease_bn', lang)}",
        "summary": _pick(rec, "summary_en", "summary_bn", lang),
        "description": _pick(rec, "summary_en", "summary_bn", lang),
        "symptoms": _pick(rec, "symptoms_en", "symptoms_bn", lang) or [],
        "treatment": treatment_bullets,
        "prevention": prevention,
        "severity": rec.get("severity"),
        "next_steps": next_steps,
        "when_to_call_helpline": _pick(rec, "when_to_call_helpline_en", "when_to_call_helpline_bn", lang),
        "expected_outcome": _pick(rec, "expected_outcome_en", "expected_outcome_bn", lang),
        "matched_key": rec.get("kb_key"),
        "class_name": rec.get("class_name"),
        "pathogen": rec.get("pathogen"),
        "treatment_plan": plan,
        "related_shop_skus": rec.get("related_shop_skus") or [],
        "is_curable_with_chemicals": rec.get("is_curable_with_chemicals"),
        "bangladesh_relevance": rec.get("bangladesh_relevance"),
        "source": rec.get("source"),
        "confidence": rec.get("confidence"),
        "from_pack": True,
    }
    if plan.get("land"):
        out["land"] = plan["land"]
    return out
