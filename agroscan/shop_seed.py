"""Import Bangladesh data pack into the shop SQLite database."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agroscan.bd_data import equipment, products, suppliers, upazilas
from agroscan.shop_db import _connect, init_shop_db

_PACK = Path(__file__).resolve().parents[1] / "data" / "agroscan"


def _product_image_map() -> dict:
    path = _PACK / "product_images.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _short_desc_map() -> dict:
    path = _PACK / "product_short_descriptions.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _image_url_for(sku: str, imap: dict) -> str | None:
    meta = imap.get(sku) or {}
    if isinstance(meta, str):
        return meta
    path = meta.get("path") if isinstance(meta, dict) else None
    return path or None


def _short_description(p: dict, dmap: dict) -> str:
    sku = p.get("sku") or ""
    if sku and dmap.get(sku):
        return str(dmap[sku]).strip()
    for key in (
        "usage_summary_en",
        "description_en",
        "typical_use_en",
        "specs_en",
        "usage_summary_bn",
        "description_bn",
        "typical_use_bn",
    ):
        val = (p.get(key) or "").strip()
        if val:
            val = " ".join(val.split())
            return val[:140] + ("…" if len(val) > 140 else "")
    name = p.get("name_en") or p.get("name") or "Farm product"
    sub = p.get("subcategory") or p.get("category") or "agro"
    return f"{sub.capitalize()} — {name}"[:140]


def seed_from_pack(replace_catalog: bool = True) -> dict:
    init_shop_db()
    now = datetime.now(timezone.utc).isoformat()
    n_upazila = n_sup = n_prod = n_link = 0
    imap = _product_image_map()
    dmap = _short_desc_map()
    with _connect() as con:
        if replace_catalog:
            n_orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            if n_orders == 0:
                con.execute("PRAGMA foreign_keys = OFF")
                con.execute("DELETE FROM supplier_products")
                con.execute("DELETE FROM products")
                con.execute("DELETE FROM suppliers")
                con.execute("DELETE FROM upazilas")
                con.execute("PRAGMA foreign_keys = ON")

        for u in upazilas():
            con.execute(
                """
                INSERT OR IGNORE INTO upazilas (district, district_bn, name, name_bn, lat, lng, division, upazila_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    u.get("district_en") or "",
                    u.get("district_bn") or "",
                    u.get("upazila_en") or "",
                    u.get("upazila_bn") or "",
                    u.get("lat"),
                    u.get("lng"),
                    u.get("division_en") or "",
                    u.get("upazila_id") or "",
                ),
            )
            n_upazila += 1

        for s in suppliers():
            # Official DAE offices are documented; still not phone-verified.
            verified = 1 if s.get("type") == "government_office" else 0
            con.execute(
                """
                INSERT INTO suppliers (
                    name, name_bn, phone, email, address, address_bn, district, upazila,
                    lat, lng, rank_in_upazila, rating, verified, created_at,
                    supplier_type, website, services_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s.get("name_en") or "",
                    s.get("name_bn") or "",
                    s.get("phone"),
                    s.get("email"),
                    s.get("address_en") or "",
                    s.get("address_bn") or "",
                    s.get("district") or "",
                    s.get("upazila") or "",
                    s.get("lat"),
                    s.get("lng"),
                    s.get("rank_in_upazila") or 10,
                    s.get("rating"),
                    verified,
                    now,
                    s.get("type") or "",
                    s.get("website") or "",
                    json.dumps(s.get("services_bn") or s.get("services_en") or [], ensure_ascii=False),
                ),
            )
            n_sup += 1

        def _insert_product(p: dict):
            keys = p.get("disease_keys") or []
            tags = p.get("crop_tags") or []
            if isinstance(keys, list):
                keys = ",".join(str(k) for k in keys)
            if isinstance(tags, list):
                tags = ",".join(str(k) for k in tags)
            price_mid = None
            pmin, pmax = p.get("price_bdt_min"), p.get("price_bdt_max")
            if pmin is not None and pmax is not None:
                price_mid = (float(pmin) + float(pmax)) / 2.0
            elif pmin is not None:
                price_mid = float(pmin)
            sku = p.get("sku") or ""
            image_url = _image_url_for(sku, imap) or p.get("image_url") or None
            desc_en = _short_description(p, dmap)
            desc_bn = (
                p.get("description_bn")
                or p.get("usage_summary_bn")
                or p.get("typical_use_bn")
                or ""
            )
            con.execute(
                """
                INSERT OR REPLACE INTO products (
                    sku, name, name_bn, category, brand, unit, description, description_bn,
                    active_ingredient, disease_keys, crop_tags, image_url, created_at,
                    price_min, price_max, price_bdt, hhp, subcategory, pack_size, registration_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sku,
                    p.get("name_en") or "",
                    p.get("name_bn") or "",
                    p.get("category") or "pesticide",
                    p.get("brand") or "",
                    p.get("unit") or "pack",
                    desc_en,
                    desc_bn,
                    p.get("active_ingredient") or "",
                    keys,
                    tags,
                    image_url,
                    now,
                    pmin,
                    pmax,
                    price_mid if price_mid is not None else 100.0,
                    1 if p.get("highly_hazardous_flag") else 0,
                    p.get("subcategory") or "",
                    p.get("pack_size") or "",
                    1 if p.get("registration_verified") else 0,
                ),
            )

        for p in products():
            _insert_product(p)
            n_prod += 1
        for p in equipment():
            row = dict(p)
            row.setdefault("category", "equipment")
            _insert_product(row)
            n_prod += 1

        # Link catalogue to suppliers using the fixed product price_bdt.
        prod_rows = con.execute(
            "SELECT id, sku, price_bdt, price_min, price_max, category FROM products"
        ).fetchall()
        sup_rows = con.execute(
            """
            SELECT id FROM suppliers
            WHERE COALESCE(supplier_type,'') IN ('brand_distributor', 'government_supplier')
            """
        ).fetchall()
        if not sup_rows:
            sup_rows = con.execute("SELECT id FROM suppliers LIMIT 10").fetchall()
        for p in prod_rows:
            mid = float(p["price_bdt"] or 0)
            if mid <= 0:
                if p["price_min"] is not None and p["price_max"] is not None:
                    mid = (float(p["price_min"]) + float(p["price_max"])) / 2.0
                elif p["price_min"] is not None:
                    mid = float(p["price_min"])
                else:
                    mid = 100.0
            for s in sup_rows[:12]:
                if hash((p["id"], s["id"])) % 4 != 0:
                    continue
                con.execute(
                    """
                    INSERT OR IGNORE INTO supplier_products (supplier_id, product_id, price_bdt, stock)
                    VALUES (?, ?, ?, ?)
                    """,
                    (s["id"], p["id"], mid, 50),
                )
                n_link += 1

    return {
        "upazilas": n_upazila,
        "suppliers": n_sup,
        "products": n_prod,
        "listings": n_link,
        "images": sum(1 for v in imap.values() if v),
        "ok": True,
    }


def apply_product_images() -> dict:
    """Update image_url + short descriptions on existing products (no catalog wipe)."""
    init_shop_db()
    imap = _product_image_map()
    dmap = _short_desc_map()
    updated_img = 0
    updated_desc = 0
    with _connect() as con:
        for sku, meta in imap.items():
            url = _image_url_for(sku, {sku: meta})
            if not url:
                continue
            cur = con.execute(
                "UPDATE products SET image_url = ? WHERE sku = ?",
                (url, sku),
            )
            updated_img += cur.rowcount or 0
        # Fill empty / placeholder descriptions from short-desc map or keep pack text
        rows = con.execute("SELECT id, sku, description FROM products").fetchall()
        pack_by_sku = {}
        for p in list(products()) + list(equipment()):
            s = p.get("sku")
            if s:
                pack_by_sku[str(s)] = p
        for r in rows:
            sku = r["sku"] or ""
            desc = dmap.get(sku) or _short_description(pack_by_sku.get(sku) or {"sku": sku, "name_en": sku}, dmap)
            if not desc:
                continue
            cur = con.execute(
                "UPDATE products SET description = ? WHERE id = ?",
                (desc, r["id"]),
            )
            updated_desc += cur.rowcount or 0
    return {
        "ok": True,
        "updated": updated_img,
        "updated_images": updated_img,
        "updated_descriptions": updated_desc,
        "mapped": len(imap),
    }


if __name__ == "__main__":
    print(seed_from_pack())
