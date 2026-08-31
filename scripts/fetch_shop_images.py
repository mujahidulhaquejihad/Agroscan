"""
Fetch Creative Commons shop photos via Openverse (no Wikimedia — avoids 429s).
Matches images to product names / active ingredients; falls back by subcategory.

Usage:
  python -u scripts/fetch_shop_images.py
  python -u scripts/fetch_shop_images.py --limit 30
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "agroscan"
OUT_DIR = ROOT / "web" / "shop-images"
MAP_PATH = PACK / "product_images.json"
UA = "AgroScanShopImages/1.1 (local agro shop; CC via Openverse)"
OPENVERSE = "https://api.openverse.org/v1/images/"

SUB_QUERIES = {
    "fungicide": [
        "fungicide spray field",
        "crop spraying fungicide",
        "plant disease spray agriculture",
    ],
    "insecticide": [
        "insecticide spray farm",
        "pest control agriculture spray",
        "farmer spraying insecticide",
    ],
    "herbicide": [
        "herbicide weed control",
        "weed spraying farm",
        "glyphosate sprayer field",
    ],
    "fertilizer": [
        "fertilizer bag farm",
        "urea fertilizer agriculture",
        "applying fertilizer field",
    ],
    "seed": [
        "crop seeds packet",
        "rice seed bag",
        "vegetable seeds agriculture",
    ],
    "sprayer": [
        "knapsack sprayer farmer",
        "backpack sprayer agriculture",
        "manual sprayer farm",
    ],
    "irrigation": [
        "farm irrigation pipe",
        "drip irrigation agriculture",
        "water pump farm",
    ],
    "tool": [
        "farm hand tools",
        "hoe agriculture tool",
        "sickle harvest tool",
    ],
    "machine": [
        "farm machinery tractor",
        "rice transplanter",
        "agricultural machine",
    ],
    "protective": [
        "farmer protective mask pesticide",
        "gloves pesticide safety",
        "protective clothing spraying",
    ],
    "trap": ["insect pheromone trap", "yellow sticky trap insects"],
    "growth": ["plant growth fertilizer", "seedling nursery agriculture"],
    "nematicide": ["soil treatment agriculture", "farm soil pesticide"],
    "rodenticide": ["grain storage farm", "barn agriculture"],
    "acaricide": ["mite control plants", "greenhouse plant spray"],
    "equipment": ["farm equipment tools", "agricultural equipment"],
    "pesticide": ["pesticide bottle agriculture", "crop protection spray"],
}


def _get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def clean_name(name: str) -> str:
    s = name or ""
    s = re.sub(
        r"\b\d+(\.\d+)?\s*(g|kg|mg|ml|l|litre|liter|mm|cm|m|hp|cc|w|v)\b",
        " ",
        s,
        flags=re.I,
    )
    s = re.sub(r"\b\d+(\.\d+)?%\b", " ", s)
    s = re.sub(r"\b(WP|EC|SC|SL|WG|GR|SP|DF|OD|CS|ME|SG)\b", " ", s, flags=re.I)
    s = re.sub(r"[+/(),]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def primary_key(row: dict) -> str:
    ai = (row.get("active_ingredient") or "").strip()
    if ai:
        first = re.split(r"[+,;/]", ai)[0].strip().lower()
        first = re.sub(r"[^a-z0-9]+", "-", first).strip("-")
        if first:
            return first
    name = clean_name(row.get("name_en") or row.get("name") or "").lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    parts = [p for p in name.split("-") if p][:4]
    return "-".join(parts) or (row.get("subcategory") or row.get("category") or "product")


def search_terms(row: dict) -> list[str]:
    name = clean_name(row.get("name_en") or row.get("name") or "")
    sub = (row.get("subcategory") or "").strip().lower()
    cat = (row.get("category") or "").strip().lower()
    ai = (row.get("active_ingredient") or "").strip()
    terms: list[str] = []
    if name:
        terms.append(name)
        short = " ".join(name.split()[:2])
        if short and short.lower() != name.lower():
            terms.append(short)
    if ai:
        first = re.split(r"[+,;/]", ai)[0].strip()
        if first:
            terms.append(first)
            terms.append(f"{first} pesticide")
    for q in SUB_QUERIES.get(sub) or SUB_QUERIES.get(cat) or SUB_QUERIES["pesticide"]:
        terms.append(q)
    if cat == "equipment" or row.get("_source") == "equipment":
        terms.extend(SUB_QUERIES.get("equipment", []))
    seen, out = set(), []
    for t in terms:
        t = re.sub(r"\s+", " ", t).strip()
        k = t.lower()
        if len(t) < 3 or k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def openverse_search(query: str, page: int = 1) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "page": page,
            "page_size": 8,
            "license_type": "commercial",
        }
    )
    try:
        data = json.loads(_get(f"{OPENVERSE}?{params}").decode("utf-8"))
        return list(data.get("results") or [])
    except Exception:
        params = urllib.parse.urlencode({"q": query, "page": page, "page_size": 8})
        try:
            data = json.loads(_get(f"{OPENVERSE}?{params}").decode("utf-8"))
            return list(data.get("results") or [])
        except Exception as exc:
            print(f"  search fail [{query}]: {exc}", flush=True)
            return []


def pick_from_results(results: list[dict], used_urls: set[str]) -> dict | None:
    ranked = []
    for r in results:
        url = r.get("url") or ""
        if not url or url in used_urls:
            continue
        lic = (r.get("license") or "").lower()
        score = 0
        if "nc" not in lic:
            score += 2
        if (r.get("category") or "") == "photograph" or "photo" in (r.get("filetype") or ""):
            score += 1
        ranked.append((score, r))
    ranked.sort(key=lambda x: -x[0])
    return ranked[0][1] if ranked else None


_query_cache: dict[str, list[dict]] = {}


def pick_image(terms: list[str], used_urls: set[str]) -> dict | None:
    for i, q in enumerate(terms):
        if q not in _query_cache:
            _query_cache[q] = openverse_search(q)
            time.sleep(0.7)
        hit = pick_from_results(_query_cache[q], used_urls)
        if hit:
            hit = dict(hit)
            hit["_query"] = q
            return hit
        # try next page once for primary term
        if i == 0:
            more = openverse_search(q, page=2)
            time.sleep(0.7)
            _query_cache[q] = (_query_cache.get(q) or []) + more
            hit = pick_from_results(_query_cache[q], used_urls)
            if hit:
                hit = dict(hit)
                hit["_query"] = q
                return hit
    return None


def download_image(url: str, dest_stub: Path) -> Path | None:
    try:
        data = _get(url, timeout=60)
    except urllib.error.HTTPError as e:
        print(f"  download HTTP {e.code}", flush=True)
        return None
    except Exception as e:
        print(f"  download error: {e}", flush=True)
        return None
    if len(data) < 1200:
        return None
    ext = ".jpg"
    low = url.lower()
    if ".png" in low or data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    elif ".webp" in low:
        ext = ".webp"
    path = dest_stub.with_suffix(ext)
    path.write_bytes(data)
    return path


def load_catalog() -> list[dict]:
    rows: list[dict] = []
    for fname, source in (("products.json", "product"), ("equipment.json", "equipment")):
        data = json.loads((PACK / fname).read_text(encoding="utf-8"))
        for row in data:
            row = dict(row)
            row["_source"] = source
            if source == "equipment":
                row.setdefault("category", "equipment")
            rows.append(row)
    return rows


def file_key(pkey: str) -> str:
    digest = hashlib.sha1(pkey.encode("utf-8")).hexdigest()[:8]
    safe = re.sub(r"[^a-z0-9]+", "-", pkey.lower()).strip("-")[:40] or "product"
    return f"{safe}-{digest}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_catalog()
    if args.limit:
        rows = rows[: args.limit]

    existing = {}
    if MAP_PATH.exists() and not args.force:
        try:
            existing = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(primary_key(row), []).append(row)

    mapping = dict(existing)
    used_urls: set[str] = set()
    for meta in mapping.values():
        if isinstance(meta, dict) and meta.get("source_url"):
            used_urls.add(meta["source_url"])

    keys = list(groups.keys())
    print(f"SKUs={len(rows)} unique_keys={len(keys)}", flush=True)

    for i, pkey in enumerate(keys, 1):
        group = groups[pkey]
        skus = [str(r.get("sku") or "") for r in group if r.get("sku")]
        fkey = file_key(pkey)
        existing_file = None
        for cand in OUT_DIR.glob(fkey + ".*"):
            existing_file = cand
            break

        if existing_file and not args.force and skus and all(s in mapping for s in skus):
            rel = f"/static/shop-images/{existing_file.name}"
            for sku in skus:
                mapping.setdefault(sku, {"path": rel, "query": pkey})
                mapping[sku]["path"] = rel
            print(f"[{i}/{len(keys)}] skip {fkey}", flush=True)
            continue

        terms = search_terms(group[0])
        print(f"[{i}/{len(keys)}] {fkey} ← {terms[0] if terms else pkey}", flush=True)
        hit = pick_image(terms, used_urls)
        if not hit:
            print("  NO IMAGE", flush=True)
            continue

        src = hit.get("url") or ""
        written = download_image(src, OUT_DIR / fkey)
        if not written:
            continue
        used_urls.add(src)
        rel = f"/static/shop-images/{written.name}"
        meta = {
            "path": rel,
            "query": hit.get("_query") or pkey,
            "title": hit.get("title") or "",
            "license": hit.get("license") or "",
            "source_url": hit.get("foreign_landing_url") or src,
            "creator": hit.get("creator") or "",
        }
        for sku in skus:
            mapping[sku] = meta
        print(f"  OK {written.name} x{len(skus)} via '{meta['query']}'", flush=True)
        # checkpoint often
        if i % 10 == 0:
            MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.35)

    MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {MAP_PATH} entries={len(mapping)} files={len(list(OUT_DIR.glob('*')))}", flush=True)


if __name__ == "__main__":
    main()
