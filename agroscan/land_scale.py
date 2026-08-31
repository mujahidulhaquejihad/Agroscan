"""Scale Bangladesh pack doses / spray water by farmer land size."""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple


def to_decimals(land_size: float, land_unit: str = "decimal") -> float:
    """Convert farmer area to decimals (1 bigha ≈ 33 decimal, 1 acre ≈ 100 decimal)."""
    try:
        size = float(land_size)
    except (TypeError, ValueError):
        size = 0.0
    if size <= 0:
        return 0.0
    unit = (land_unit or "decimal").strip().lower()
    if unit in ("bigha", "বিঘা", "biga"):
        return size * 33.0
    if unit in ("acre", "একর"):
        return size * 100.0
    if unit in ("hectare", "ha", "হেক্টর"):
        return size * 247.1
    return size  # decimal / শতাংশ


def _first_range(text: str) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[–\-to]+\s*(\d+(?:\.\d+)?)",
        str(text),
        flags=re.IGNORECASE,
    )
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return (min(a, b), max(a, b))
    m = re.search(r"(\d+(?:\.\d+)?)", str(text))
    if m:
        v = float(m.group(1))
        return (v, v)
    return None


def water_litres_per_decimal(water_text: str) -> Optional[Tuple[float, float]]:
    """Parse pack strings like '4-5 litres of spray solution per decimal...'."""
    if not water_text:
        return None
    # Prefer the per-decimal figure if both decimal and bigha appear.
    lower = str(water_text).lower()
    head = water_text
    if "per bigha" in lower or "বিঘা" in water_text:
        # Take text before bigha note when possible
        cut = re.split(r"\(|per bigha|বিঘা", water_text, maxsplit=1, flags=re.IGNORECASE)[0]
        head = cut or water_text
    return _first_range(head)


def dose_per_litre(dose_text: str) -> Optional[Tuple[float, float, str]]:
    """Return (lo, hi, unit) for rates like '0.6 g per litre' / Bangla equivalents."""
    if not dose_text:
        return None
    t = str(dose_text)
    # g/ml/kg per litre (EN + BN)
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:[–\-]\s*(\d+(?:\.\d+)?))?\s*"
        r"(g|gram|grams|ml|mL|kg|গ্রাম|মিলি)\s*"
        r"(?:per\s*litre|/\s*L|প্রতি\s*লিটার|/লিটার)",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2) or m.group(1))
        unit = m.group(3).lower()
        if unit in ("gram", "grams", "গ্রাম"):
            unit = "g"
        elif unit in ("মিলি",):
            unit = "ml"
        return (min(lo, hi), max(lo, hi), unit)

    # "6 g per 10 litre sprayer"
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(g|ml|গ্রাম|মিলি)\s*per\s*(\d+(?:\.\d+)?)\s*litre",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        amt = float(m.group(1))
        unit = m.group(2).lower()
        litres = float(m.group(3)) or 1.0
        if unit in ("গ্রাম",):
            unit = "g"
        elif unit in ("মিলি",):
            unit = "ml"
        rate = amt / litres
        return (rate, rate, unit)

    # Bangla: প্রতি লিটার পানিতে ০.৬ গ্রাম — digits may be ASCII in pack
    m = re.search(
        r"প্রতি\s*লিটার[^\d]*(\d+(?:\.\d+)?)\s*(গ্রাম|মিলি|g|ml)",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        v = float(m.group(1))
        unit = m.group(2).lower()
        if unit == "গ্রাম":
            unit = "g"
        elif unit == "মিলি":
            unit = "ml"
        return (v, v, unit)
    return None


def kg_per_bigha(text: str) -> Optional[Tuple[float, float]]:
    """Parse '5-7 kg ... per bigha' style fertilizer lines."""
    if not text:
        return None
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*[–\-]\s*(\d+(?:\.\d+)?)\s*kg[^\n]{0,40}per\s*bigha",
        str(text),
        flags=re.IGNORECASE,
    )
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return (min(a, b), max(a, b))
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*kg[^\n]{0,40}per\s*bigha",
        str(text),
        flags=re.IGNORECASE,
    )
    if m:
        v = float(m.group(1))
        return (v, v)
    m = re.search(
        r"বিঘা\s*প্রতি[^\d]*(\d+(?:\.\d+)?)\s*[–\-]?\s*(\d+(?:\.\d+)?)?\s*কেজি",
        str(text),
    )
    if m:
        a = float(m.group(1))
        b = float(m.group(2) or m.group(1))
        return (min(a, b), max(a, b))
    return None


def land_band(decimals: float) -> str:
    if decimals <= 0:
        return "unknown"
    if decimals < 5:
        return "small"
    if decimals < 33:
        return "medium"
    return "large"


def followup_steps(decimals: float, lang: str = "bn") -> list[dict]:
    """Extra land-size-aware follow-ups (prevention / monitoring)."""
    band = land_band(decimals)
    bn = (lang or "en").startswith("bn")
    if band == "small":
        if bn:
            return [
                {
                    "title": "ছোট জমি — পুরো প্লট দেখুন",
                    "detail": f"আপনার প্রায় {decimals:.1f} শতাংশ জমি। প্রতিদিন সব গাছ ঘুরে দেখুন। "
                    "হাত স্প্রেয়ার বা ৮–১৬ লিটার ন্যাপস্যাকই যথেষ্ট।",
                },
                {
                    "title": "৩ ও ৭ দিন পর আবার স্ক্যান",
                    "detail": "স্প্রের ৩ দিন পর এবং ৭ দিন পর একই জায়গার পাতার ছবি তুলে AgroScan দিয়ে দেখুন রোগ থেমেছে কিনা।",
                },
            ]
        return [
            {
                "title": "Small plot — walk the whole field",
                "detail": f"About {decimals:.1f} decimal. Check every plant daily. "
                "A hand or 8–16 L knapsack sprayer is enough.",
            },
            {
                "title": "Re-check on day 3 and day 7",
                "detail": "Photograph the same area 3 and 7 days after spraying and scan again with AgroScan.",
            },
        ]
    if band == "medium":
        if bn:
            return [
                {
                    "title": "মাঝারি জমি — জোন ভাগ করুন",
                    "detail": f"প্রায় {decimals:.1f} শতাংশ। জমিকে ২–৩ ভাগে ভাগ করে স্প্রে ও স্কাউটিং করুন; "
                    "প্রতি ২ মিটারে হাঁটার ফাঁক রাখুন।",
                },
                {
                    "title": "হটস্পট আগে স্প্রে",
                    "detail": "যেখানে দাগ বেশি সেখান থেকে শুরু করুন, তারপর সুস্থ অংশে প্রতিরোধমূলক স্প্রে। "
                    "৭–১০ দিন পর পুরো জমি ঘুরে দেখুন।",
                },
            ]
        return [
            {
                "title": "Medium plot — spray in zones",
                "detail": f"About {decimals:.1f} decimal. Split into 2–3 blocks for spraying and scouting; "
                "keep walking gaps every 2 m.",
            },
            {
                "title": "Treat hotspots first",
                "detail": "Start where spots are worst, then protect cleaner areas. Walk the whole field again in 7–10 days.",
            },
        ]
    # large
    if bn:
        return [
            {
                "title": "বড় জমি — অগ্রাধিকার ও সাহায্য",
                "detail": f"প্রায় {decimals:.1f} শতাংশ (~{decimals/33:.1f} বিঘা)। "
                "প্রথমে সবচেয়ে আক্রান্ত ব্লক; প্রয়োজনে মোটর স্প্রেয়ার বা শ্রমিক নিন।",
            },
            {
                "title": "গ্রাম পর্যায়ে সমন্বয়",
                "detail": "রোগ ছড়াচ্ছে দেখলে উপজেলা কৃষি অফিস বা ১৬১২৩-এ খবর দিন — বড় জমিতে একক স্প্রে যথেষ্ট নাও হতে পারে।",
            },
            {
                "title": "সাপ্তাহিক মনিটরিং",
                "detail": "প্রতি সপ্তাহে ক্রস-ওয়াক করে ২০–৩০ গাছ পরীক্ষা করুন; সীমানা ও নিচু জায়গায় বেশি নজর দিন।",
            },
        ]
    return [
        {
            "title": "Large field — prioritise and get help",
            "detail": f"About {decimals:.1f} decimal (~{decimals/33:.1f} bigha). "
            "Treat the worst blocks first; consider motorised spray or hired labour.",
        },
        {
            "title": "Coordinate locally",
            "detail": "If disease is spreading, contact the Upazila Agriculture Office or 16123 — "
            "one solo spray may not be enough on a large plot.",
        },
        {
            "title": "Weekly monitoring",
            "detail": "Cross-walk weekly and check 20–30 plants; watch borders and low spots.",
        },
    ]


def scale_chemical(ct: dict, decimals: float, lang: str = "bn") -> dict:
    """Attach land-scaled spray water and product amount estimates."""
    out: dict[str, Any] = {}
    if decimals <= 0:
        return out

    water_text = ct.get("water_volume_per_decimal") or ""
    water = water_litres_per_decimal(str(water_text))
    dose_text = ct.get("dose_en") or ct.get("dose_bn") or ""
    dose = dose_per_litre(str(dose_text))

    bn = (lang or "en").startswith("bn")
    out["land_decimals"] = round(decimals, 2)
    out["water_volume_per_decimal"] = water_text

    if water:
        w_lo, w_hi = water
        tot_lo, tot_hi = w_lo * decimals, w_hi * decimals
        out["spray_water_l_per_decimal"] = [w_lo, w_hi]
        out["spray_water_litres"] = [round(tot_lo, 1), round(tot_hi, 1)]
        out["knapsack_loads_16l"] = [
            max(1, int(round(tot_lo / 16.0 + 0.49))),
            max(1, int(round(tot_hi / 16.0 + 0.49))),
        ]
        if dose:
            d_lo, d_hi, unit = dose
            p_lo, p_hi = d_lo * tot_lo, d_hi * tot_hi
            out["product_rate_per_litre"] = [d_lo, d_hi]
            out["product_unit"] = unit
            out["product_amount"] = [round(p_lo, 1), round(p_hi, 1)]
            if bn:
                out["dose_scaled"] = (
                    f"আপনার জমির জন্য আনুমানিক স্প্রে পানি {tot_lo:.0f}–{tot_hi:.0f} লিটার "
                    f"(~{out['knapsack_loads_16l'][0]}–{out['knapsack_loads_16l'][1]} বার ১৬লি ন্যাপস্যাক)। "
                    f"মোট ওষুধ প্রায় {p_lo:.1f}–{p_hi:.1f} {unit}। "
                    f"লেবেলের হার ({d_lo} {unit}/লিটার) মেনে মিশিয়ে নিন।"
                )
            else:
                out["dose_scaled"] = (
                    f"For your plot: about {tot_lo:.0f}–{tot_hi:.0f} L spray mix "
                    f"(~{out['knapsack_loads_16l'][0]}–{out['knapsack_loads_16l'][1]} × 16 L loads). "
                    f"Product needed ≈ {p_lo:.1f}–{p_hi:.1f} {unit}. "
                    f"Mix at the label rate ({d_lo} {unit}/L)."
                )
        else:
            if bn:
                out["dose_scaled"] = (
                    f"আপনার জমির জন্য আনুমানিক স্প্রে পানি {tot_lo:.0f}–{tot_hi:.0f} লিটার "
                    f"(শতাংশপ্রতি {w_lo}–{w_hi} লিটার)। প্যাকেটের লেবেল অনুযায়ী ওষুধ মিশিয়ে নিন।"
                )
            else:
                out["dose_scaled"] = (
                    f"For your plot: about {tot_lo:.0f}–{tot_hi:.0f} L spray water "
                    f"({w_lo}–{w_hi} L per decimal). Mix product per the pack label."
                )
    elif dose:
        d_lo, d_hi, unit = dose
        # Assume mid 4.5 L/decimal if pack omitted water volume
        assume = 4.5 * decimals
        p_lo, p_hi = d_lo * assume, d_hi * assume
        out["spray_water_litres"] = [round(assume * 0.9, 1), round(assume * 1.1, 1)]
        out["product_amount"] = [round(p_lo, 1), round(p_hi, 1)]
        out["product_unit"] = unit
        if bn:
            out["dose_scaled"] = (
                f"পানির পরিমাণ প্যাক থেকে পাওয়া যায়নি; আনুমানিক {assume:.0f} লিটার পানিতে "
                f"প্রায় {p_lo:.1f}–{p_hi:.1f} {unit} ওষুধ (হার {d_lo} {unit}/লিটার)। লেবেল যাচাই করুন।"
            )
        else:
            out["dose_scaled"] = (
                f"Water volume missing in pack; estimate ~{assume:.0f} L water with "
                f"{p_lo:.1f}–{p_hi:.1f} {unit} product at {d_lo} {unit}/L. Verify on the label."
            )
    return out


def scale_fertilizer_note(text: str, decimals: float, lang: str = "bn") -> Optional[str]:
    if not text or decimals <= 0:
        return None
    rng = kg_per_bigha(text)
    if not rng:
        return None
    lo, hi = rng
    bighas = decimals / 33.0
    t_lo, t_hi = lo * bighas, hi * bighas
    bn = (lang or "en").startswith("bn")
    if bn:
        return (
            f"আপনার জমির (~{decimals:.1f} শতাংশ / {bighas:.2f} বিঘা) জন্য আনুমানিক "
            f"{t_lo:.1f}–{t_hi:.1f} কেজি (বিঘাপ্রতি {lo}–{hi} কেজি হারে)। মাটি পরীক্ষা ও FRG অনুসরণ করুন।"
        )
    return (
        f"For your plot (~{decimals:.1f} decimal / {bighas:.2f} bigha): about "
        f"{t_lo:.1f}–{t_hi:.1f} kg at {lo}–{hi} kg per bigha. Follow soil test / FRG where available."
    )


def land_summary(decimals: float, land_size: float, land_unit: str, lang: str = "bn") -> str:
    bn = (lang or "en").startswith("bn")
    band = land_band(decimals)
    band_bn = {"small": "ছোট", "medium": "মাঝারি", "large": "বড়", "unknown": ""}.get(band, "")
    band_en = band
    if bn:
        return (
            f"জমির হিসাব: {land_size:g} {land_unit} ≈ {decimals:.1f} শতাংশ "
            f"({band_bn} প্লট)। নিচের মাত্রা এই আকার অনুযায়ী আনুমানিক — প্যাকেটের লেবেলই চূড়ান্ত।"
        )
    return (
        f"Land used: {land_size:g} {land_unit} ≈ {decimals:.1f} decimal "
        f"({band_en} plot). Amounts below are estimates for this size — the pack label is final."
    )
