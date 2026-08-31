"""Commerce database: suppliers, products, orders.

Production recommendation: PostgreSQL 15+ with PostGIS for upazila/location
queries and concurrent order processing. SQLite is used here for local dev
and single-server deploy; schema mirrors PostgreSQL tables for easy migration.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agrovet.config import SHOP_DB_PATH

ORDER_STATUSES = ("pending", "confirmed", "processing", "shipped", "delivered", "cancelled")
PRODUCT_CATEGORIES = ("pesticide", "medicine", "seed", "fertilizer", "equipment")


def _connect():
    SHOP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(SHOP_DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_shop_db():
    with _connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS upazilas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                district TEXT NOT NULL,
                district_bn TEXT,
                name TEXT NOT NULL,
                name_bn TEXT,
                lat REAL,
                lng REAL,
                UNIQUE(district, name)
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_bn TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                district TEXT NOT NULL,
                upazila TEXT NOT NULL,
                lat REAL,
                lng REAL,
                rank_in_upazila INTEGER DEFAULT 10,
                rating REAL DEFAULT 4.0,
                verified INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_suppliers_loc ON suppliers(district, upazila);

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                name_bn TEXT,
                category TEXT NOT NULL,
                brand TEXT,
                unit TEXT DEFAULT 'piece',
                description TEXT,
                description_bn TEXT,
                active_ingredient TEXT,
                disease_keys TEXT,
                crop_tags TEXT,
                image_url TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category);

            CREATE TABLE IF NOT EXISTS supplier_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                price_bdt REAL NOT NULL,
                stock INTEGER DEFAULT 100,
                min_order_qty REAL DEFAULT 1,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY(product_id) REFERENCES products(id),
                UNIQUE(supplier_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                user_name TEXT,
                user_phone TEXT,
                district TEXT,
                upazila TEXT,
                address TEXT,
                lat REAL,
                lng REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_bdt REAL DEFAULT 0,
                notes TEXT,
                admin_notes TEXT,
                supplier_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
            );
            CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                qty REAL NOT NULL,
                unit_price_bdt REAL NOT NULL,
                line_total_bdt REAL NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS order_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                actor TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            );
            """
        )
        _ensure_columns(con)


def _ensure_columns(con):
    extra = {
        "upazilas": [("division", "TEXT"), ("upazila_id", "TEXT"), ("district_bn", "TEXT")],
        "suppliers": [
            ("supplier_type", "TEXT"),
            ("website", "TEXT"),
            ("services_json", "TEXT"),
            ("address_bn", "TEXT"),
        ],
        "products": [
            ("price_min", "REAL"),
            ("price_max", "REAL"),
            ("price_bdt", "REAL"),
            ("hhp", "INTEGER DEFAULT 0"),
            ("subcategory", "TEXT"),
            ("pack_size", "TEXT"),
            ("registration_verified", "INTEGER DEFAULT 0"),
        ],
    }
    for table, cols in extra.items():
        existing = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
    try:
        con.execute(
            """
            UPDATE products
            SET price_bdt = CASE
                WHEN price_min IS NOT NULL AND price_max IS NOT NULL THEN (price_min + price_max) / 2.0
                WHEN price_min IS NOT NULL THEN price_min
                WHEN price_max IS NOT NULL THEN price_max
                ELSE 100.0
            END
            WHERE price_bdt IS NULL OR price_bdt <= 0
            """
        )
    except Exception:
        pass


def product_price(product_id: int) -> float:
    """Fixed shop price for a product (admin-editable)."""
    with _connect() as con:
        row = con.execute(
            "SELECT price_bdt, price_min, price_max FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    if not row:
        return 0.0
    if row["price_bdt"] is not None and float(row["price_bdt"]) > 0:
        return round(float(row["price_bdt"]), 2)
    if row["price_min"] is not None and row["price_max"] is not None:
        return round((float(row["price_min"]) + float(row["price_max"])) / 2.0, 2)
    if row["price_min"] is not None:
        return round(float(row["price_min"]), 2)
    return 0.0


def update_product_price(product_id: int, price_bdt: float) -> dict:
    price = float(price_bdt)
    if price < 0:
        raise ValueError("Price cannot be negative.")
    with _connect() as con:
        cur = con.execute(
            "UPDATE products SET price_bdt = ? WHERE id = ?",
            (price, product_id),
        )
        if cur.rowcount == 0:
            raise ValueError("Product not found.")
        con.execute(
            "UPDATE supplier_products SET price_bdt = ? WHERE product_id = ?",
            (price, product_id),
        )
        con.commit()
        row = con.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _row_dict(row)


def list_products_admin(search: str = "", limit: int = 100, offset: int = 0) -> List[dict]:
    return list_products(search=search, limit=limit, offset=offset)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def list_upazilas(district: str = "") -> List[dict]:
    with _connect() as con:
        if district:
            rows = con.execute(
                "SELECT * FROM upazilas WHERE district = ? ORDER BY name",
                (district,),
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM upazilas ORDER BY district, name").fetchall()
    if rows:
        out = [_row_dict(r) for r in rows]
        return _enrich_upazila_bn(out)
    try:
        from agrovet.bd_data import upazilas as pack_upazilas

        out = []
        for u in pack_upazilas():
            if district and str(u.get("district_en") or "") != district:
                continue
            out.append(
                {
                    "district": u.get("district_en"),
                    "district_bn": u.get("district_bn"),
                    "name": u.get("upazila_en"),
                    "name_bn": u.get("upazila_bn"),
                    "lat": u.get("lat"),
                    "lng": u.get("lng"),
                    "division": u.get("division_en"),
                }
            )
        return out
    except Exception:
        return []


def _enrich_upazila_bn(rows: List[dict]) -> List[dict]:
    """Fill missing Bangla district/upazila names from the data pack."""
    need = any(not (r.get("district_bn") and r.get("name_bn")) for r in rows)
    if not need:
        return rows
    try:
        from agrovet.bd_data import upazilas as pack_upazilas

        dmap = {}
        umap = {}
        for u in pack_upazilas():
            den = str(u.get("district_en") or "")
            uen = str(u.get("upazila_en") or "")
            if den and u.get("district_bn"):
                dmap[den] = u.get("district_bn")
            if den and uen and u.get("upazila_bn"):
                umap[(den, uen)] = u.get("upazila_bn")
        for r in rows:
            den = str(r.get("district") or "")
            uen = str(r.get("name") or "")
            if not r.get("district_bn") and den in dmap:
                r["district_bn"] = dmap[den]
            if not r.get("name_bn") and (den, uen) in umap:
                r["name_bn"] = umap[(den, uen)]
    except Exception:
        pass
    return rows

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


def nearest_upazila(lat: float, lng: float) -> Optional[dict]:
    """Return closest upazila centroid to device GPS (plus distance_km)."""
    rows = list_upazilas()
    best = None
    best_d = None
    for u in rows:
        try:
            ulat = float(u.get("lat"))
            ulng = float(u.get("lng"))
        except (TypeError, ValueError):
            continue
        d = _haversine_km(float(lat), float(lng), ulat, ulng)
        if best_d is None or d < best_d:
            best_d = d
            best = dict(u)
    if not best or best_d is None:
        return None
    best["distance_km"] = round(best_d, 2)
    best["lat_query"] = float(lat)
    best["lng_query"] = float(lng)
    return best


def list_suppliers(
    district: str = "",
    upazila: str = "",
    limit: int = 10,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> List[dict]:
    q = "SELECT * FROM suppliers WHERE 1=1"
    params: list = []
    if district:
        q += " AND district = ?"
        params.append(district)
    if upazila:
        q += " AND upazila = ?"
        params.append(upazila)
    # Pull a wider set when sorting by GPS distance.
    fetch_n = max(limit * 5, 40) if lat is not None and lng is not None else limit
    q += " ORDER BY rank_in_upazila ASC, COALESCE(rating, 0) DESC LIMIT ?"
    params.append(fetch_n)
    with _connect() as con:
        rows = con.execute(q, params).fetchall()
    out = [_row_dict(r) for r in rows]
    if lat is not None and lng is not None:
        scored = []
        for s in out:
            try:
                slat = float(s.get("lat"))
                slng = float(s.get("lng"))
                dist = _haversine_km(float(lat), float(lng), slat, slng)
            except (TypeError, ValueError):
                dist = 1e9
            s = dict(s)
            s["distance_km"] = None if dist >= 1e9 else round(dist, 2)
            scored.append((dist, s))
        scored.sort(key=lambda t: (t[0], t[1].get("rank_in_upazila") or 99))
        out = [s for _, s in scored[:limit]]
    else:
        out = out[:limit]
    return out


def list_products(
    category: str = "",
    search: str = "",
    disease_key: str = "",
    crop: str = "",
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    q = "SELECT * FROM products WHERE 1=1"
    params: list = []
    if category:
        q += " AND category = ?"
        params.append(category)
    if search:
        q += " AND (name LIKE ? OR name_bn LIKE ? OR brand LIKE ? OR sku LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if disease_key:
        q += " AND disease_keys LIKE ?"
        params.append(f"%{disease_key}%")
    if crop:
        q += " AND crop_tags LIKE ?"
        params.append(f"%{crop}%")
    q += " ORDER BY category, name LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect() as con:
        rows = con.execute(q, params).fetchall()
    out = []
    for r in rows:
        item = _row_dict(r)
        pb = item.get("price_bdt")
        if pb is None or float(pb or 0) <= 0:
            pmin, pmax = item.get("price_min"), item.get("price_max")
            if pmin is not None and pmax is not None:
                pb = (float(pmin) + float(pmax)) / 2.0
            elif pmin is not None:
                pb = float(pmin)
            else:
                pb = 0.0
        item["price_bdt"] = round(float(pb), 2)
        out.append(item)
    return out


def product_with_suppliers(product_id: int, district: str = "", upazila: str = "") -> Optional[dict]:
    with _connect() as con:
        p = con.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not p:
            return None
        out = _row_dict(p)
        sq = """
            SELECT sp.*, s.name AS supplier_name, s.phone, s.district, s.upazila, s.rank_in_upazila
            FROM supplier_products sp
            JOIN suppliers s ON s.id = sp.supplier_id
            WHERE sp.product_id = ?
        """
        params: list = [product_id]
        if district:
            sq += " AND s.district = ?"
            params.append(district)
        if upazila:
            sq += " AND s.upazila = ?"
            params.append(upazila)
        sq += " ORDER BY s.rank_in_upazila ASC, sp.price_bdt ASC"
        out["listings"] = [_row_dict(r) for r in con.execute(sq, params).fetchall()]
        return out


def recommended_products_for_disease(disease_class: str, district: str = "", upazila: str = "") -> List[dict]:
    skus: List[str] = []
    try:
        from agrovet.bd_data import find_treatment

        rec = find_treatment(class_name=disease_class)
        if rec:
            for item in rec.get("related_shop_skus") or []:
                sku = item.get("sku") if isinstance(item, dict) else None
                if sku:
                    skus.append(str(sku))
    except Exception:
        pass
    out: List[dict] = []
    seen = set()
    with _connect() as con:
        for sku in skus:
            if sku in seen:
                continue
            seen.add(sku)
            row = con.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
            if not row:
                continue
            item = _row_dict(row)
            listings = con.execute(
                """
                SELECT sp.price_bdt, s.name AS supplier_name, s.phone, s.district, s.upazila
                FROM supplier_products sp JOIN suppliers s ON s.id = sp.supplier_id
                WHERE sp.product_id = ?
                ORDER BY s.rank_in_upazila ASC LIMIT 3
                """,
                (item["id"],),
            ).fetchall()
            item["listings"] = [_row_dict(x) for x in listings]
            out.append(item)
        if out:
            return out
        from agrovet.knowledge import advice_for

        info = advice_for(disease_class, "en") or {}
        tp = info.get("treatment_plan") or {}
        names = []
        for ct in tp.get("chemical_treatments") or []:
            if isinstance(ct, dict):
                ai = ct.get("active_ingredient") or ct.get("product_en") or ""
                if ai:
                    names.append(ai)
        for ai in names:
            rows = con.execute(
                "SELECT * FROM products WHERE active_ingredient LIKE ? OR name LIKE ? LIMIT 5",
                (f"%{ai}%", f"%{ai}%"),
            ).fetchall()
            for r in rows:
                item = _row_dict(r)
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                item["listings"] = []
                out.append(item)
    return out


def _order_code() -> str:
    return "AV" + secrets.token_hex(4).upper()


def create_order(
    items: List[Dict[str, Any]],
    user_id: Optional[int] = None,
    user_name: str = "",
    user_phone: str = "",
    district: str = "",
    upazila: str = "",
    address: str = "",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    supplier_id: Optional[int] = None,
    notes: str = "",
) -> dict:
    if not items:
        raise ValueError("Order must have at least one item.")
    now = _now()
    code = _order_code()
    total = 0.0
    with _connect() as con:
        priced = []
        for it in items:
            pid = int(it["product_id"])
            qty = float(it.get("qty", 1))
            row = con.execute(
                "SELECT name, price_bdt, price_min, price_max FROM products WHERE id = ?",
                (pid,),
            ).fetchone()
            if not row:
                raise ValueError(f"Product {pid} not found.")
            price = float(row["price_bdt"] or 0)
            if price <= 0:
                if row["price_min"] is not None and row["price_max"] is not None:
                    price = (float(row["price_min"]) + float(row["price_max"])) / 2.0
                elif row["price_min"] is not None:
                    price = float(row["price_min"])
            price = round(price, 2)
            priced.append((pid, row["name"], qty, price))
            total += price * qty
        cur = con.execute(
            """
            INSERT INTO orders (order_code, user_id, user_name, user_phone, district, upazila,
                address, lat, lng, status, total_bdt, notes, supplier_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (
                code,
                user_id,
                user_name,
                user_phone,
                district,
                upazila,
                address,
                lat,
                lng,
                total,
                notes,
                supplier_id,
                now,
                now,
            ),
        )
        oid = cur.lastrowid
        for pid, name, qty, price in priced:
            con.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, qty, unit_price_bdt, line_total_bdt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (oid, pid, name, qty, price, price * qty),
            )
        con.execute(
            "INSERT INTO order_events (order_id, status, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
            (oid, "pending", "Order placed by farmer", user_name or "farmer", now),
        )
        order = con.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    return get_order(order["order_code"])  # type: ignore


def get_order(order_code: str) -> dict:
    with _connect() as con:
        o = con.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,)).fetchone()
        if not o:
            raise ValueError("Order not found.")
        out = _row_dict(o)
        out["items"] = [
            _row_dict(r)
            for r in con.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
        ]
        out["events"] = [
            _row_dict(r)
            for r in con.execute(
                "SELECT * FROM order_events WHERE order_id = ? ORDER BY id", (o["id"],)
            ).fetchall()
        ]
        return out


def list_orders(
    user_id: Optional[int] = None,
    status: str = "",
    limit: int = 50,
) -> List[dict]:
    q = "SELECT * FROM orders WHERE 1=1"
    params: list = []
    if user_id is not None:
        q += " AND user_id = ?"
        params.append(user_id)
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as con:
        rows = con.execute(q, params).fetchall()
    return [_row_dict(r) for r in rows]


def admin_shop_stats() -> dict:
    init_shop_db()
    with _connect() as con:
        products = con.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        suppliers = con.execute("SELECT COUNT(*) AS c FROM suppliers").fetchone()["c"]
        orders = con.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        revenue = con.execute(
            "SELECT COALESCE(SUM(total_bdt),0) AS s FROM orders WHERE status != 'cancelled'"
        ).fetchone()["s"]
        by_status = {
            r["status"]: int(r["c"])
            for r in con.execute(
                "SELECT status, COUNT(*) AS c FROM orders GROUP BY status"
            ).fetchall()
        }
        pending = int(by_status.get("pending", 0))
    return {
        "products": int(products),
        "suppliers": int(suppliers),
        "orders": int(orders),
        "orders_pending": pending,
        "revenue_bdt": round(float(revenue or 0), 2),
        "orders_by_status": by_status,
    }


def update_order_status(order_code: str, status: str, message: str = "", actor: str = "admin") -> dict:
    if status not in ORDER_STATUSES:
        raise ValueError("Invalid status.")
    now = _now()
    with _connect() as con:
        o = con.execute("SELECT id FROM orders WHERE order_code = ?", (order_code,)).fetchone()
        if not o:
            raise ValueError("Order not found.")
        con.execute(
            "UPDATE orders SET status = ?, updated_at = ?, admin_notes = COALESCE(admin_notes,'') || ? WHERE order_code = ?",
            (status, now, f"\n[{now}] {message}" if message else "", order_code),
        )
        con.execute(
            "INSERT INTO order_events (order_id, status, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
            (o["id"], status, message or f"Status -> {status}", actor, now),
        )
    return get_order(order_code)
