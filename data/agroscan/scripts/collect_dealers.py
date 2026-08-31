#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgroScan — dealer collection script (Section D, Phase 1 completion)
===================================================================

WHY THIS SCRIPT EXISTS
----------------------
suppliers.json ships with government offices, BADC and brand distributors only.
Real agro-input dealers with real phone numbers were deliberately NOT invented,
because the research brief forbids fake phone numbers and no public dataset of
Bangladeshi upazila agro-dealers exists.

This script fills that gap legitimately, using the Google Places API, which
returns business names, addresses, coordinates, phone numbers and ratings under
Google's terms of service.

BEFORE YOU RUN IT
-----------------
1. Get a Google Cloud API key with "Places API (New)" enabled.
2. Read Google's Places API policy on caching and display. In short: you may
   cache Place IDs indefinitely, but other Places data (name, address, phone,
   rating) may generally only be cached for a limited period and must be
   refreshed. Build your DB refresh cycle accordingly, and attribute Google
   where the policy requires it.
3. Budget: Text Search is billed per request. 15 upazilas x 6 query variants
   x up to 3 pages is roughly 270 requests for Phase 1 — small. Scaling to all
   495 upazilas is roughly 9,000 requests, so check current pricing first.

WHAT IT DOES
------------
For each upazila, runs several Bangla and English query variants, deduplicates
by place_id, fetches phone number and opening hours via Place Details, and
writes suppliers_collected.json in the AgroScan Section D schema with
verified=false. A human still has to call each number before flipping
verified=true — a Google listing being present does not mean the shop is open,
still trading, or licensed.

IMPORTANT: cross-check the result against the LICENSED DEALER REGISTER held by
the Upazila Agriculture Office. A shop appearing on Google Maps is not proof it
holds a pesticide dealer licence under the Pesticide Act 2018. Only list dealers
you can confirm are licensed, or clearly mark licence status as unknown in the app.

USAGE
-----
    export GOOGLE_MAPS_API_KEY=...
    python3 collect_dealers.py --out suppliers_collected.json
    python3 collect_dealers.py --all-upazilas --upazilas ../upazilas.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

PLACES_TEXT_SEARCH = "https://places.googleapis.com/v1/places:searchText"

# Query variants. Bangla queries matter: many rural agro-shops are only listed
# in Bangla, and an English-only search misses a large share of them.
QUERY_TEMPLATES = [
    "কৃষি বীজ ও সার দোকান {upazila} {district}",
    "সার ও কীটনাশক ডিলার {upazila} {district}",
    "কৃষি ভান্ডার {upazila}",
    "agro input dealer {upazila} {district} Bangladesh",
    "fertilizer shop {upazila} {district} Bangladesh",
    "pesticide seed dealer {upazila} {district} Bangladesh",
]

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.regularOpeningHours",
    "places.businessStatus",
    "places.types",
    "places.googleMapsUri",
])

PHASE1 = [
    ("Dhaka", "Savar"), ("Dhaka", "Dhamrai"), ("Dhaka", "Keraniganj"),
    ("Gazipur", "Kaliakair"), ("Gazipur", "Kapasia"),
    ("Mymensingh", "Trishal"), ("Mymensingh", "Gafargaon"),
    ("Rajshahi", "Paba"), ("Rajshahi", "Tanore"),
    ("Khulna", "Dumuria"), ("Khulna", "Digholia"),
    ("Sylhet", "Golapganj"), ("Sylhet", "Beanibazar"),
    ("Barisal", "Babuganj"), ("Rangpur", "Badargonj"),
]


def text_search(api_key: str, query: str, lat: float | None = None,
                lng: float | None = None, radius_m: int = 25000) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"textQuery": query, "languageCode": "bn", "regionCode": "BD"}
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {"center": {"latitude": lat, "longitude": lng},
                       "radius": float(radius_m)}
        }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    r = requests.post(PLACES_TEXT_SEARCH, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        print(f"  ! {r.status_code} for query {query!r}: {r.text[:200]}", file=sys.stderr)
        return []
    return r.json().get("places", [])


def to_agroscan(place: dict[str, Any], district: str, upazila: str,
                rank: int) -> dict[str, Any]:
    name = (place.get("displayName") or {}).get("text")
    loc = place.get("location") or {}
    hours = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions")
    return {
        "name_en": name,
        "name_bn": name,                      # Google often returns the Bangla name already
        "type": "dealer",
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "email": None,
        "address_en": place.get("formattedAddress"),
        "address_bn": place.get("formattedAddress"),
        "district": district,
        "upazila": upazila,
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "rank_in_upazila": rank,
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "business_status": place.get("businessStatus"),
        "verified": False,
        "licence_status": "unknown",
        "products_sold": ["pesticide", "seed", "fertilizer"],
        "brands_stocked": [],
        "delivery_available": None,
        "payment_methods": [],
        "opening_hours_en": " | ".join(hours) if hours else None,
        "opening_hours_bn": None,
        "google_place_id": place.get("id"),
        "google_maps_uri": place.get("googleMapsUri"),
        "source": place.get("googleMapsUri") or "Google Places API",
        "source_type": "field_guide",
        "last_verified": time.strftime("%Y-%m-%d"),
        "confidence": "low",
        "notes": ("Collected automatically from Google Places. NOT verified by phone and "
                  "licence status NOT checked against the Upazila Agriculture Office "
                  "licensed-dealer register. Do not present as a recommended dealer until "
                  "both checks are done."),
    }


def collect(api_key: str, targets: list[tuple[str, str]],
            centroids: dict[tuple[str, str], tuple[float, float]] | None,
            sleep: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for district, upazila in targets:
        print(f"[{district} / {upazila}]")
        seen: dict[str, dict[str, Any]] = {}
        c = (centroids or {}).get((district, upazila))
        for tmpl in QUERY_TEMPLATES:
            q = tmpl.format(district=district, upazila=upazila)
            places = text_search(api_key, q,
                                 lat=c[0] if c else None,
                                 lng=c[1] if c else None)
            for p in places:
                pid = p.get("id")
                if pid and pid not in seen:
                    seen[pid] = p
            time.sleep(sleep)
        # rank by rating x log(review count) so a 5.0 with one review does not
        # outrank a 4.3 with forty
        def score(p: dict[str, Any]) -> float:
            import math
            return float(p.get("rating") or 0) * math.log1p(p.get("userRatingCount") or 0)

        ranked = sorted(seen.values(), key=score, reverse=True)[:10]
        for i, p in enumerate(ranked, start=1):
            out.append(to_agroscan(p, district, upazila, i))
        print(f"  -> {len(ranked)} kept out of {len(seen)} unique places")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="suppliers_collected.json")
    ap.add_argument("--upazilas", help="path to upazilas.json for centroids and full coverage")
    ap.add_argument("--all-upazilas", action="store_true",
                    help="collect for all 494 upazilas instead of the 15 Phase-1 ones")
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        sys.exit("Set GOOGLE_MAPS_API_KEY in the environment.")

    centroids = None
    targets = PHASE1
    if args.upazilas:
        rows = json.load(open(args.upazilas, encoding="utf-8"))
        centroids = {(r["district_en"], r["upazila_en"]): (r["lat"], r["lng"]) for r in rows}
        if args.all_upazilas:
            targets = [(r["district_en"], r["upazila_en"]) for r in rows]
    elif args.all_upazilas:
        sys.exit("--all-upazilas requires --upazilas pointing at upazilas.json")

    recs = collect(api_key, targets, centroids, args.sleep)
    json.dump(recs, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with_phone = sum(1 for r in recs if r["phone"])
    print(f"\nWrote {len(recs)} records to {args.out} ({with_phone} with a phone number).")
    print("NEXT STEPS, in order:")
    print("  1. Call each number and confirm the shop trades in agro-inputs.")
    print("  2. Check the licence against the Upazila Agriculture Office dealer register.")
    print("  3. Only then set verified=true and licence_status.")
    print("  4. Re-run periodically; Places data must be refreshed per Google's caching policy.")


if __name__ == "__main__":
    main()
