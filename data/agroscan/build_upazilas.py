#!/usr/bin/env python3
"""
AgroScan Section E — build upazilas.json
Joins the nuhil/bangladesh-geocode administrative hierarchy (division/district/
upazila with Bangla names) to geoBoundaries gbOpen BGD ADM3 polygon centroids.

Outputs: data/upazilas.json  +  data/upazilas_unmatched.json (QA)
"""
import json, re, unicodedata, difflib
from shapely.geometry import shape, Point

D = "/root/agroscan/data/"


def phpmyadmin_rows(path):
    blob = json.load(open(path, encoding="utf-8"))
    for chunk in blob:
        if chunk.get("type") == "table":
            return chunk["data"]
    raise ValueError("no table chunk in " + path)


divisions = phpmyadmin_rows(D + "divisions_raw.json")
districts = phpmyadmin_rows(D + "districts_raw.json")
upazilas = phpmyadmin_rows(D + "upazilas_raw.json")

div_by_id = {d["id"]: d for d in divisions}
dis_by_id = {d["id"]: d for d in districts}

adm3 = json.load(open(D + "bgd_adm3.geojson", encoding="utf-8"))["features"]
adm2 = json.load(open(D + "bgd_adm2.geojson", encoding="utf-8"))["features"]

# district polygons for point-in-polygon assignment
adm2_shapes = [(f["properties"]["shapeName"], shape(f["geometry"])) for f in adm2]


def norm(s):
    """Aggressive transliteration-tolerant key. Bangla place names are romanised
    inconsistently across datasets (Faridgonj/Faridganj, Senbug/Senbagh,
    Ukhiya/Ukhia, Laxmichhari/Lakshmichari), so collapse the usual variants."""
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    for w in ("upazila", "upazilla", "thana", "paurashava", "pourashava"):
        s = s.replace(w, "")
    s = s.replace(" ", "")
    # transliteration collapses, longest first
    rules = [
        ("ksh", "kh"), ("laksh", "lakh"), ("x", "ks"),
        ("chh", "ch"), ("sh", "s"), ("zh", "j"), ("z", "j"),
        ("ph", "f"), ("bh", "b"), ("dh", "d"), ("th", "t"),
        ("kh", "k"), ("gh", "g"), ("jh", "j"), ("ch", "c"),
        ("ee", "i"), ("oo", "u"), ("y", "i"), ("w", "u"),
        ("gonj", "ganj"), ("gong", "gang"), ("aa", "a"), ("ou", "o"),
        ("v", "b"), ("q", "k"),
    ]
    for a, b in rules:
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)          # collapse doubles
    s = re.sub(r"[aeiou]+$", "", s)           # trailing vowels (Ukhiya/Ukhia)
    return s


# ---- 1:1 district-name reconciliation between the two sources -----------
# Several districts were officially renamed (Bogra->Bogura, Jessore->Jashore,
# Comilla->Cumilla, Chittagong->Chattogram, Barisal->Barishal). Rather than
# hand-maintaining aliases, solve the 64<->64 assignment greedily by similarity.
gc_districts = [d["name"] for d in districts]
gb_districts = [f["properties"]["shapeName"] for f in adm2]
# manual anchors for renames where string similarity is weak
ANCHOR = {"Cumilla": "Comilla", "Chattogram": "Chittagong",
          "Chapainawabganj": "Nawabganj", "Coxsbazar": "Cox'S Bazar"}

pairs = []
for a in gc_districts:
    for b in gb_districts:
        s = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
        if ANCHOR.get(a) == b:
            s = 2.0
        pairs.append((s, a, b))
pairs.sort(reverse=True)
gc2gb, used_a, used_b = {}, set(), set()
for s, a, b in pairs:
    if a in used_a or b in used_b:
        continue
    gc2gb[a] = b
    used_a.add(a)
    used_b.add(b)
assert len(gc2gb) == 64, len(gc2gb)
weak = {a: (b, round(difflib.SequenceMatcher(None, norm(a), norm(b)).ratio(), 2))
        for a, b in gc2gb.items()
        if difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() < 0.75}
print("weak district pairings (review):", weak)


def dnorm_gc(name):
    """district key for a geocode district name"""
    return norm(gc2gb[name])


def dnorm_gb(name):
    return norm(name)


# ---- pre-compute ADM3 centroids + their district ------------------------
adm3_recs = []
for f in adm3:
    g = shape(f["geometry"])
    c = g.representative_point()  # guaranteed inside the polygon
    name = f["properties"]["shapeName"]
    dist = None
    for dn, dg in adm2_shapes:
        if dg.contains(c):
            dist = dn
            break
    if dist is None:  # fall back to nearest district polygon
        dist = min(adm2_shapes, key=lambda t: t[1].distance(c))[0]
    adm3_recs.append({"name": name, "n": norm(name), "district": dist,
                      "dn": dnorm_gb(dist), "lat": round(c.y, 6),
                      "lng": round(c.x, 6), "area": g.area})

SOURCE = ("https://github.com/nuhil/bangladesh-geocode (administrative hierarchy "
          "+ official Bangla names, derived from BBS/bdgov geocodes) joined to "
          "geoBoundaries gbOpen BGD ADM3 polygons (https://www.geoboundaries.org)")

CONF = {
    "exact_name_in_district": "high",
    "manual_name_override": "high",
    "partial_name_in_district": "medium",
    "fuzzy_name_in_district": "medium",
    "exact_name_any_district": "medium",
    "partial_name_any_district": "low",
    "parent_upazila_polygon": "low",
    "district_centroid_fallback": "low",
}
NOTE = {
    "parent_upazila_polygon": (
        "This upazila was carved out of a parent upazila after the boundary "
        "dataset vintage. The point lies inside the PARENT upazila, so it is "
        "directionally right but not this upazila's own centroid. Replace with a "
        "surveyed point before using for delivery-radius logic."),
    "district_centroid_fallback": (
        "No matching ADM3 polygon found; the DISTRICT centroid is used as a "
        "placeholder. Do not use for distance ranking without replacing."),
}
DEFAULT_NOTE = ("Interior representative point of the upazila polygon (guaranteed "
                "to fall inside the boundary), not the town centre or upazila "
                "headquarters. Suitable for map defaults and distance sorting; "
                "not for navigation.")


def make_record(div, dis, u, lat, lng, shape_name, match_q):
    return {
        "division_en": div["name"],
        "division_bn": div["bn_name"],
        "district_en": dis["name"],
        "district_bn": dis["bn_name"],
        "upazila_en": u["name"],
        "upazila_bn": u["bn_name"],
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
        "upazila_id": int(u["id"]),
        "district_id": int(u["district_id"]),
        "division_id": int(dis["division_id"]),
        "gov_url": u.get("url"),
        "centroid_method": ("adm2_district_centroid"
                            if match_q == "district_centroid_fallback"
                            else "adm3_representative_point"),
        "match_quality": match_q,
        "geoboundaries_shape_name": shape_name,
        "source": SOURCE,
        "source_type": "official",
        "last_verified": "2026-08-19",
        "confidence": CONF[match_q],
        "notes": NOTE.get(match_q, DEFAULT_NOTE),
    }


# ---- explicit overrides -------------------------------------------------
# (district_en, upazila_en) -> (geoBoundaries ADM3 shapeName, is_parent_polygon)
# geoBoundaries' BGD ADM3 vintage predates several upazilas that were carved out
# of a parent upazila. For those we deliberately borrow the PARENT polygon's
# interior point and flag confidence "low" — the point is inside the correct
# general area but is not the new upazila's own centroid.
OVERRIDE = {
    ("Comilla", "Sadarsouth"): ("Comilla Sadar Dakshin", False),
    ("Chandpur", "Matlab North"): ("Matlab Uttar", False),
    ("Chandpur", "Matlab South"): ("Matlab Dakshin", False),
    ("Sunamganj", "South Sunamganj"): ("Dakshin Sunamganj", False),
    ("Jashore", "Jessore Sadar"): ("Kotwali", False),
    ("Chattogram", "Karnafuli"): ("Patiya", True),        # split from Patiya, 2000
    ("Khagrachhari", "Guimara"): ("Matiranga", True),     # split 2014
    ("Natore", "Naldanga"): ("Natore Sadar", True),       # split 2013
    ("Patuakhali", "Rangabali"): ("Galachipa", True),     # split 2012
    ("Sylhet", "Osmaninagar"): ("Balaganj", True),        # split 2013
    ("Sunamganj", "Madhyanagar"): ("Dharampasha", True),  # split 2022
    ("Mymensingh", "Tarakanda"): ("Phulpur", True),       # split 2015
    ("Coxsbazar", "Eidgaon"): ("Cox's Bazar Sadar", True),  # split 2021
    ("Madaripur", "Dasar"): ("Kalkini", True),            # split 2021
}
by_shapename = {}
for r in adm3_recs:
    by_shapename.setdefault(r["name"], r)

out, unmatched, parent_derived = [], [], []
for u in upazilas:
    dis = dis_by_id[u["district_id"]]
    div = div_by_id[dis["division_id"]]
    un, dn = norm(u["name"]), dnorm_gc(dis["name"])

    ov = OVERRIDE.get((dis["name"], u["name"]))
    if ov and ov[0] in by_shapename:
        r = by_shapename[ov[0]]
        parent = ov[1]
        out.append(make_record(div, dis, u, r["lat"], r["lng"], r["name"],
                               "parent_upazila_polygon" if parent
                               else "manual_name_override"))
        if parent:
            parent_derived.append(f'{u["name"]} ({dis["name"]}) <- {ov[0]}')
        continue

    # 1) exact name match inside the same district
    cand = [r for r in adm3_recs if r["n"] == un and r["dn"] == dn]
    match_q = "exact_name_in_district"
    if not cand:  # 2) prefix/contains match inside the same district
        cand = [r for r in adm3_recs
                if r["dn"] == dn and (r["n"].startswith(un) or un.startswith(r["n"]))]
        match_q = "partial_name_in_district"
    if not cand:  # 3) exact name anywhere (district naming mismatch)
        cand = [r for r in adm3_recs if r["n"] == un]
        match_q = "exact_name_any_district"
    if not cand:  # 4) fuzzy match inside the same district
        pool = [r for r in adm3_recs if r["dn"] == dn]
        scored = [(difflib.SequenceMatcher(None, un, r["n"]).ratio(), r) for r in pool]
        scored = [t for t in scored if t[0] >= 0.72]
        if scored:
            cand = [max(scored, key=lambda t: t[0])[1]]
            match_q = "fuzzy_name_in_district"
    if not cand:  # 5) contains match anywhere
        cand = [r for r in adm3_recs if un and (un in r["n"] or r["n"] in un)]
        match_q = "partial_name_any_district"

    if cand:
        best = max(cand, key=lambda r: r["area"])
        lat, lng, src_name = best["lat"], best["lng"], best["name"]
    else:
        lat, lng = float(dis["lat"]), float(dis["lon"])
        src_name = None
        match_q = "district_centroid_fallback"
        unmatched.append({"upazila": u["name"], "district": dis["name"]})

    out.append(make_record(div, dis, u, lat, lng, src_name, match_q))

out.sort(key=lambda r: (r["division_en"], r["district_en"], r["upazila_en"]))
json.dump(out, open(D + "upazilas.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

qa = {"generated": "2026-08-19",
      "total": len(out),
      "unmatched_district_centroid_fallback": unmatched,
      "parent_polygon_derived": parent_derived}
json.dump(qa, open(D + "upazilas_qa.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

from collections import Counter
print("records:", len(out))
print("districts:", len({r["district_en"] for r in out}),
      "divisions:", len({r["division_en"] for r in out}))
print(Counter(r["match_quality"] for r in out))
print(Counter(r["confidence"] for r in out))
print("parent-derived:", len(parent_derived))
print("fallback:", len(unmatched), unmatched)
# sanity: every point must sit inside Bangladesh's bbox
bad = [r for r in out if not (20.5 <= r["lat"] <= 26.7 and 88.0 <= r["lng"] <= 92.7)]
print("outside BD bbox:", bad)
