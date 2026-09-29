"""Commerce database: suppliers, products, orders.

Production recommendation: PostgreSQL 15+ with PostGIS for upazila/location
queries and concurrent order processing. SQLite is used here for local dev
and single-server deploy; schema mirrors PostgreSQL tables for easy migration.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agroscan.auth_store import _check_password, _hash_password
from agroscan.config import SHOP_DB_PATH

DEFAULT_VENDOR_USER = "vendor"
DEFAULT_VENDOR_PASSWORD = "agroscan-vendor"
VENDOR_SESSION_DAYS = 30

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

            CREATE TABLE IF NOT EXISTS vendor_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                supplier_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
            );
            CREATE INDEX IF NOT EXISTS idx_vendor_supplier ON vendor_accounts(supplier_id);

            CREATE TABLE IF NOT EXISTS vendor_sessions (
                token TEXT PRIMARY KEY,
                vendor_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(vendor_id) REFERENCES vendor_accounts(id)
            );
            """
        )
        _ensure_columns(con)
    _ensure_default_vendor()


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
        from agroscan.bd_data import upazilas as pack_upazilas

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
        from agroscan.bd_data import upazilas as pack_upazilas

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
        from agroscan.bd_data import find_treatment

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
        from agroscan.knowledge import advice_for

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
    actor: str = "farmer",
) -> dict:
    if not items:
        raise ValueError("Order must have at least one item.")
    now = _now()
    code = _order_code()
    total = 0.0
    if not supplier_id:
        supplier_id = pick_supplier_id(district, upazila, lat, lng)
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
            if supplier_id:
                con.execute(
                    """
                    UPDATE supplier_products
                    SET stock = MAX(0, COALESCE(stock, 0) - ?)
                    WHERE supplier_id = ? AND product_id = ?
                    """,
                    (qty, supplier_id, pid),
                )
        who = (actor or "farmer").strip() or "farmer"
        con.execute(
            "INSERT INTO order_events (order_id, status, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
            (oid, "pending", "Order placed by " + who, user_name or who, now),
        )
        order = con.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    return get_order(order["order_code"])  # type: ignore


def get_order(order_code: str) -> dict:
    with _connect() as con:
        o = con.execute(
            """
            SELECT o.*, s.name AS supplier_name, s.phone AS supplier_phone
            FROM orders o
            LEFT JOIN suppliers s ON s.id = o.supplier_id
            WHERE o.order_code = ?
            """,
            (order_code,),
        ).fetchone()
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
    supplier_id: Optional[int] = None,
    search: str = "",
    limit: int = 50,
    unassigned: bool = False,
) -> List[dict]:
    q = """
        SELECT o.*, s.name AS supplier_name,
               (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.id) AS item_count
        FROM orders o
        LEFT JOIN suppliers s ON s.id = o.supplier_id
        WHERE 1=1
    """
    params: list = []
    if user_id is not None:
        q += " AND o.user_id = ?"
        params.append(user_id)
    if status:
        q += " AND o.status = ?"
        params.append(status)
    if supplier_id is not None:
        q += " AND o.supplier_id = ?"
        params.append(supplier_id)
    if unassigned:
        q += " AND o.supplier_id IS NULL"
    if search:
        like = f"%{search.strip()}%"
        q += """ AND (
            o.order_code LIKE ? OR o.user_name LIKE ? OR o.user_phone LIKE ?
            OR o.address LIKE ? OR COALESCE(s.name,'') LIKE ?
        )"""
        params.extend([like, like, like, like, like])
    q += " ORDER BY o.id DESC LIMIT ?"
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
        unassigned = con.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE supplier_id IS NULL"
        ).fetchone()["c"]
        vendors = con.execute("SELECT COUNT(*) AS c FROM vendor_accounts").fetchone()["c"]
    return {
        "products": int(products),
        "suppliers": int(suppliers),
        "orders": int(orders),
        "orders_pending": pending,
        "orders_unassigned": int(unassigned),
        "vendors": int(vendors),
        "revenue_bdt": round(float(revenue or 0), 2),
        "orders_by_status": by_status,
    }


def update_order_status(
    order_code: str,
    status: str,
    message: str = "",
    actor: str = "admin",
    supplier_id: Optional[int] = None,
) -> dict:
    if status not in ORDER_STATUSES:
        raise ValueError("Invalid status.")
    now = _now()
    with _connect() as con:
        o = con.execute(
            "SELECT id, supplier_id FROM orders WHERE order_code = ?",
            (order_code,),
        ).fetchone()
        if not o:
            raise ValueError("Order not found.")
        if supplier_id is not None and int(o["supplier_id"] or 0) != int(supplier_id):
            raise ValueError("Not your order.")
        con.execute(
            "UPDATE orders SET status = ?, updated_at = ?, admin_notes = COALESCE(admin_notes,'') || ? WHERE order_code = ?",
            (status, now, f"\n[{now}] {message}" if message else "", order_code),
        )
        con.execute(
            "INSERT INTO order_events (order_id, status, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
            (o["id"], status, message or f"Status -> {status}", actor, now),
        )
    return get_order(order_code)


def update_order(
    order_code: str,
    *,
    user_name: Optional[str] = None,
    user_phone: Optional[str] = None,
    district: Optional[str] = None,
    upazila: Optional[str] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
    supplier_id: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    actor: str = "admin",
) -> dict:
    """Edit customer fields and/or replace line items. Stock is not rewound on item edits."""
    now = _now()
    with _connect() as con:
        o = con.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,)).fetchone()
        if not o:
            raise ValueError("Order not found.")
        oid = int(o["id"])
        next_name = o["user_name"] if user_name is None else str(user_name).strip()
        next_phone = o["user_phone"] if user_phone is None else str(user_phone).strip()
        next_district = o["district"] if district is None else str(district).strip()
        next_upazila = o["upazila"] if upazila is None else str(upazila).strip()
        next_address = o["address"] if address is None else str(address).strip()
        next_notes = o["notes"] if notes is None else str(notes).strip()
        next_supplier = o["supplier_id"] if supplier_id is None else int(supplier_id)
        if supplier_id is not None:
            s = con.execute("SELECT id, name FROM suppliers WHERE id = ?", (next_supplier,)).fetchone()
            if not s:
                raise ValueError("Supplier not found.")
        total = float(o["total_bdt"] or 0)
        if items is not None:
            if not items:
                raise ValueError("Order must have at least one item.")
            priced = []
            total = 0.0
            for it in items:
                pid = int(it["product_id"])
                qty = float(it.get("qty", 1))
                if qty <= 0:
                    raise ValueError("Quantity must be greater than 0.")
                row = con.execute(
                    "SELECT name, price_bdt, price_min, price_max FROM products WHERE id = ?",
                    (pid,),
                ).fetchone()
                if not row:
                    raise ValueError(f"Product {pid} not found.")
                price = float(it.get("unit_price_bdt") or 0) or float(row["price_bdt"] or 0)
                if price <= 0:
                    if row["price_min"] is not None and row["price_max"] is not None:
                        price = (float(row["price_min"]) + float(row["price_max"])) / 2.0
                    elif row["price_min"] is not None:
                        price = float(row["price_min"])
                price = round(price, 2)
                priced.append((pid, row["name"], qty, price))
                total += price * qty
            con.execute("DELETE FROM order_items WHERE order_id = ?", (oid,))
            for pid, name, qty, price in priced:
                con.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, product_name, qty, unit_price_bdt, line_total_bdt)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (oid, pid, name, qty, price, price * qty),
                )
        con.execute(
            """
            UPDATE orders SET user_name = ?, user_phone = ?, district = ?, upazila = ?,
                address = ?, notes = ?, supplier_id = ?, total_bdt = ?, updated_at = ?
            WHERE order_code = ?
            """,
            (
                next_name,
                next_phone,
                next_district,
                next_upazila,
                next_address,
                next_notes,
                next_supplier,
                round(total, 2),
                now,
                order_code,
            ),
        )
        con.execute(
            "INSERT INTO order_events (order_id, status, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
            (oid, o["status"] or "pending", "Order edited", actor, now),
        )
    return get_order(order_code)


def pick_supplier_id(
    district: str = "",
    upazila: str = "",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> Optional[int]:
    rows = list_suppliers(district, upazila, limit=1, lat=lat, lng=lng)
    if not rows and district:
        rows = list_suppliers(district, "", limit=1, lat=lat, lng=lng)
    if not rows:
        rows = list_suppliers("", "", limit=1, lat=lat, lng=lng)
    return int(rows[0]["id"]) if rows else None


def assign_order_supplier(order_code: str, supplier_id: int, actor: str = "admin") -> dict:
    now = _now()
    with _connect() as con:
        o = con.execute("SELECT id FROM orders WHERE order_code = ?", (order_code,)).fetchone()
        if not o:
            raise ValueError("Order not found.")
        s = con.execute("SELECT id, name FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not s:
            raise ValueError("Supplier not found.")
        con.execute(
            "UPDATE orders SET supplier_id = ?, updated_at = ? WHERE order_code = ?",
            (supplier_id, now, order_code),
        )
        con.execute(
            "INSERT INTO order_events (order_id, status, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
            (o["id"], "pending", f"Assigned to {s['name']}", actor, now),
        )
    return get_order(order_code)


def list_suppliers_admin(search: str = "", limit: int = 80, offset: int = 0) -> dict:
    q = "SELECT * FROM suppliers WHERE 1=1"
    params: list = []
    if search:
        like = f"%{search.strip()}%"
        q += " AND (name LIKE ? OR name_bn LIKE ? OR district LIKE ? OR upazila LIKE ? OR phone LIKE ?)"
        params.extend([like, like, like, like, like])
    count_q = q.replace("SELECT *", "SELECT COUNT(*) AS c", 1)
    q += " ORDER BY district, upazila, rank_in_upazila, name LIMIT ? OFFSET ?"
    params.extend([max(1, min(int(limit), 300)), max(0, int(offset))])
    with _connect() as con:
        total = con.execute(count_q, params[:-2] if search else []).fetchone()["c"]
        rows = con.execute(q, params).fetchall()
        order_counts = {
            int(r["supplier_id"]): int(r["c"])
            for r in con.execute(
                "SELECT supplier_id, COUNT(*) AS c FROM orders WHERE supplier_id IS NOT NULL GROUP BY supplier_id"
            ).fetchall()
        }
    out = []
    for r in rows:
        item = _row_dict(r)
        item["order_count"] = order_counts.get(int(item["id"]), 0)
        out.append(item)
    return {"suppliers": out, "total": int(total)}


def get_supplier(supplier_id: int) -> dict:
    with _connect() as con:
        row = con.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    if not row:
        raise ValueError("Supplier not found.")
    return _row_dict(row)


def list_supplier_listings(
    supplier_id: int,
    search: str = "",
    limit: int = 80,
    offset: int = 0,
    low_stock: bool = False,
) -> dict:
    q = """
        SELECT p.*, sp.price_bdt AS listing_price_bdt, sp.stock, sp.min_order_qty
        FROM supplier_products sp
        JOIN products p ON p.id = sp.product_id
        WHERE sp.supplier_id = ?
    """
    params: list = [supplier_id]
    if search:
        like = f"%{search.strip()}%"
        q += " AND (p.name LIKE ? OR p.name_bn LIKE ? OR p.sku LIKE ? OR p.brand LIKE ?)"
        params.extend([like, like, like, like])
    if low_stock:
        q += " AND COALESCE(sp.stock, 0) <= 5"
    count_sql = "SELECT COUNT(*) AS c FROM (" + q + ")"
    q += " ORDER BY p.category, p.name LIMIT ? OFFSET ?"
    params.extend([max(1, min(int(limit), 300)), max(0, int(offset))])
    with _connect() as con:
        total = con.execute(count_sql, params[:-2]).fetchone()["c"]
        rows = con.execute(q, params).fetchall()
    out = []
    for r in rows:
        item = _row_dict(r)
        item["price_bdt"] = round(float(item.get("listing_price_bdt") or item.get("price_bdt") or 0), 2)
        item["stock"] = int(item.get("stock") or 0)
        out.append(item)
    return {"products": out, "total": int(total)}


def update_supplier_listing(
    supplier_id: int,
    product_id: int,
    price_bdt: Optional[float] = None,
    stock: Optional[int] = None,
) -> dict:
    with _connect() as con:
        row = con.execute(
            "SELECT id FROM supplier_products WHERE supplier_id = ? AND product_id = ?",
            (supplier_id, product_id),
        ).fetchone()
        if not row:
            raise ValueError("Listing not found.")
        if price_bdt is not None:
            if float(price_bdt) < 0:
                raise ValueError("Price cannot be negative.")
            con.execute(
                "UPDATE supplier_products SET price_bdt = ? WHERE id = ?",
                (float(price_bdt), row["id"]),
            )
        if stock is not None:
            if int(stock) < 0:
                raise ValueError("Stock cannot be negative.")
            con.execute(
                "UPDATE supplier_products SET stock = ? WHERE id = ?",
                (int(stock), row["id"]),
            )
        con.commit()
    with _connect() as con:
        hit = con.execute(
            """
            SELECT p.*, sp.price_bdt AS listing_price_bdt, sp.stock, sp.min_order_qty
            FROM supplier_products sp JOIN products p ON p.id = sp.product_id
            WHERE sp.supplier_id = ? AND sp.product_id = ?
            """,
            (supplier_id, product_id),
        ).fetchone()
    item = _row_dict(hit)
    item["price_bdt"] = round(float(item.get("listing_price_bdt") or 0), 2)
    item["stock"] = int(item.get("stock") or 0)
    return item


def upsert_supplier_listing(
    supplier_id: int,
    product_id: int,
    price_bdt: Optional[float] = None,
    stock: Optional[int] = None,
) -> dict:
    with _connect() as con:
        prod = con.execute(
            "SELECT id, price_bdt FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not prod:
            raise ValueError("Product not found.")
        row = con.execute(
            "SELECT id FROM supplier_products WHERE supplier_id = ? AND product_id = ?",
            (supplier_id, product_id),
        ).fetchone()
        price = float(price_bdt) if price_bdt is not None else float(prod["price_bdt"] or 0)
        qty = int(stock) if stock is not None else 0
        if price < 0 or qty < 0:
            raise ValueError("Price and stock cannot be negative.")
        if row:
            con.execute(
                "UPDATE supplier_products SET price_bdt = ?, stock = ? WHERE id = ?",
                (price, qty, row["id"]),
            )
        else:
            con.execute(
                """
                INSERT INTO supplier_products (supplier_id, product_id, price_bdt, stock)
                VALUES (?, ?, ?, ?)
                """,
                (supplier_id, product_id, price, qty),
            )
    return update_supplier_listing(supplier_id, product_id)


def update_supplier_profile(
    supplier_id: int,
    *,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> dict:
    with _connect() as con:
        row = con.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not row:
            raise ValueError("Shop not found.")
        next_phone = row["phone"] if phone is None else str(phone).strip()
        next_addr = row["address"] if address is None else str(address).strip()
        con.execute(
            "UPDATE suppliers SET phone = ?, address = ? WHERE id = ?",
            (next_phone, next_addr, supplier_id),
        )
    return get_supplier(supplier_id)


def vendor_self_update(
    vendor_id: int,
    *,
    password: Optional[str] = None,
    keep_token: Optional[str] = None,
) -> None:
    if password is None or not str(password).strip():
        return
    pw = str(password).strip()
    if len(pw) < 6:
        raise ValueError("Password must be at least 6 characters.")
    with _connect() as con:
        if not con.execute("SELECT 1 FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone():
            raise ValueError("Vendor not found.")
        con.execute(
            "UPDATE vendor_accounts SET password_hash = ? WHERE id = ?",
            (_hash_password(pw), vendor_id),
        )
        if keep_token:
            con.execute(
                "DELETE FROM vendor_sessions WHERE vendor_id = ? AND token != ?",
                (vendor_id, keep_token),
            )
        else:
            con.execute("DELETE FROM vendor_sessions WHERE vendor_id = ?", (vendor_id,))


def _vendor_username(raw: str) -> str:
    name = (raw or "").strip().lower()
    if len(name) < 3 or len(name) > 32 or not all(c.isalnum() or c == "_" for c in name):
        raise ValueError("Username must be 3–32 letters, numbers, or underscore.")
    return name


def _vendor_dict(row: sqlite3.Row, supplier: Optional[dict] = None) -> dict:
    out = {
        "id": int(row["id"]),
        "username": row["username"],
        "supplier_id": int(row["supplier_id"]),
        "active": int(row["active"] or 0),
        "created_at": row["created_at"] if "created_at" in row.keys() else "",
    }
    if supplier:
        out["supplier_name"] = supplier.get("name") or ""
        out["district"] = supplier.get("district") or ""
        out["upazila"] = supplier.get("upazila") or ""
        out["phone"] = supplier.get("phone") or ""
        out["address"] = supplier.get("address") or ""
    return out


def _ensure_default_vendor() -> None:
    user = (os.environ.get("AGROSCAN_VENDOR_USER") or DEFAULT_VENDOR_USER).strip().lower() or DEFAULT_VENDOR_USER
    password = (os.environ.get("AGROSCAN_VENDOR_PASSWORD") or DEFAULT_VENDOR_PASSWORD).strip() or DEFAULT_VENDOR_PASSWORD
    with _connect() as con:
        supplier = con.execute("SELECT id FROM suppliers ORDER BY id LIMIT 1").fetchone()
        if not supplier:
            now = _now()
            cur = con.execute(
                """
                INSERT INTO suppliers (
                    name, name_bn, phone, district, upazila, rank_in_upazila, rating, verified, created_at
                ) VALUES (?, ?, ?, ?, ?, 1, 4.5, 1, ?)
                """,
                ("AgroScan Central Shop", "এগ্রোস্ক্যান কেন্দ্রীয় দোকান", "16123", "Dhaka", "Dhaka South", now),
            )
            supplier_id = int(cur.lastrowid)
        else:
            supplier_id = int(supplier["id"])
        con.execute(
            """
            UPDATE vendor_accounts
            SET supplier_id = ?
            WHERE supplier_id NOT IN (SELECT id FROM suppliers)
            """,
            (supplier_id,),
        )
        row = con.execute(
            "SELECT id, supplier_id FROM vendor_accounts WHERE username = ?",
            (user,),
        ).fetchone()
        if not row:
            con.execute(
                """
                INSERT INTO vendor_accounts (username, password_hash, supplier_id, active, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (user, _hash_password(password), supplier_id, _now()),
            )
            return
        exists = con.execute(
            "SELECT 1 FROM suppliers WHERE id = ?", (row["supplier_id"],)
        ).fetchone()
        if not exists:
            con.execute(
                "UPDATE vendor_accounts SET supplier_id = ? WHERE id = ?",
                (supplier_id, row["id"]),
            )


def list_vendors() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT v.*, s.name AS supplier_name, s.district, s.upazila, s.phone
            FROM vendor_accounts v
            LEFT JOIN suppliers s ON s.id = v.supplier_id
            ORDER BY v.id
            """
        ).fetchall()
    out = []
    for r in rows:
        item = _vendor_dict(r)
        item["supplier_name"] = r["supplier_name"] or ""
        item["district"] = r["district"] or ""
        item["upazila"] = r["upazila"] or ""
        item["phone"] = r["phone"] or ""
        out.append(item)
    return out


def create_vendor(username: str, password: str, supplier_id: int) -> dict:
    username = _vendor_username(username)
    if not (password or "").strip() or len(password.strip()) < 6:
        raise ValueError("Password must be at least 6 characters.")
    with _connect() as con:
        if not con.execute("SELECT 1 FROM suppliers WHERE id = ?", (supplier_id,)).fetchone():
            raise ValueError("Supplier not found.")
        if con.execute("SELECT 1 FROM vendor_accounts WHERE username = ?", (username,)).fetchone():
            raise ValueError("Username already taken.")
        cur = con.execute(
            """
            INSERT INTO vendor_accounts (username, password_hash, supplier_id, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (username, _hash_password(password.strip()), supplier_id, _now()),
        )
        vid = int(cur.lastrowid)
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vid,)).fetchone()
        supplier = con.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    return _vendor_dict(row, _row_dict(supplier) if supplier else None)


def reset_vendor_password(vendor_id: int, password: str) -> dict:
    if not (password or "").strip() or len(password.strip()) < 6:
        raise ValueError("Password must be at least 6 characters.")
    with _connect() as con:
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone()
        if not row:
            raise ValueError("Vendor not found.")
        con.execute(
            "UPDATE vendor_accounts SET password_hash = ? WHERE id = ?",
            (_hash_password(password.strip()), vendor_id),
        )
        con.execute("DELETE FROM vendor_sessions WHERE vendor_id = ?", (vendor_id,))
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone()
        supplier = con.execute("SELECT * FROM suppliers WHERE id = ?", (row["supplier_id"],)).fetchone()
    return _vendor_dict(row, _row_dict(supplier) if supplier else None)


def update_vendor(
    vendor_id: int,
    *,
    username: Optional[str] = None,
    supplier_id: Optional[int] = None,
    password: Optional[str] = None,
    active: Optional[int] = None,
) -> dict:
    with _connect() as con:
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone()
        if not row:
            raise ValueError("Vendor not found.")
        next_user = row["username"] if username is None else _vendor_username(username)
        next_sid = int(row["supplier_id"]) if supplier_id is None else int(supplier_id)
        next_active = int(row["active"] or 0) if active is None else (1 if active else 0)
        if supplier_id is not None:
            if not con.execute("SELECT 1 FROM suppliers WHERE id = ?", (next_sid,)).fetchone():
                raise ValueError("Supplier not found.")
        if username is not None:
            clash = con.execute(
                "SELECT id FROM vendor_accounts WHERE username = ? AND id != ?",
                (next_user, vendor_id),
            ).fetchone()
            if clash:
                raise ValueError("Username already taken.")
        con.execute(
            "UPDATE vendor_accounts SET username = ?, supplier_id = ?, active = ? WHERE id = ?",
            (next_user, next_sid, next_active, vendor_id),
        )
        if password is not None and str(password).strip():
            if len(str(password).strip()) < 6:
                raise ValueError("Password must be at least 6 characters.")
            con.execute(
                "UPDATE vendor_accounts SET password_hash = ? WHERE id = ?",
                (_hash_password(str(password).strip()), vendor_id),
            )
            con.execute("DELETE FROM vendor_sessions WHERE vendor_id = ?", (vendor_id,))
        if active is not None and not next_active:
            con.execute("DELETE FROM vendor_sessions WHERE vendor_id = ?", (vendor_id,))
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone()
        supplier = con.execute("SELECT * FROM suppliers WHERE id = ?", (row["supplier_id"],)).fetchone()
    return _vendor_dict(row, _row_dict(supplier) if supplier else None)


def set_vendor_active(vendor_id: int, active: int) -> dict:
    with _connect() as con:
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone()
        if not row:
            raise ValueError("Vendor not found.")
        con.execute("UPDATE vendor_accounts SET active = ? WHERE id = ?", (1 if active else 0, vendor_id))
        if not active:
            con.execute("DELETE FROM vendor_sessions WHERE vendor_id = ?", (vendor_id,))
        row = con.execute("SELECT * FROM vendor_accounts WHERE id = ?", (vendor_id,)).fetchone()
        supplier = con.execute("SELECT * FROM suppliers WHERE id = ?", (row["supplier_id"],)).fetchone()
    return _vendor_dict(row, _row_dict(supplier) if supplier else None)


def vendor_login(username: str, password: str) -> dict:
    username = (username or "").strip().lower()
    with _connect() as con:
        row = con.execute(
            "SELECT * FROM vendor_accounts WHERE username = ?",
            (username,),
        ).fetchone()
        if not row or not _check_password(password or "", row["password_hash"]):
            raise ValueError("Wrong username or password.")
        if int(row["active"] or 0) != 1:
            raise ValueError("This vendor account is disabled.")
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=VENDOR_SESSION_DAYS)).isoformat()
        con.execute(
            "INSERT INTO vendor_sessions (token, vendor_id, expires_at) VALUES (?, ?, ?)",
            (token, row["id"], expires),
        )
        supplier = con.execute("SELECT * FROM suppliers WHERE id = ?", (row["supplier_id"],)).fetchone()
    return {
        "token": token,
        "vendor": _vendor_dict(row, _row_dict(supplier) if supplier else None),
    }


def vendor_logout(token: str) -> None:
    if not token:
        return
    with _connect() as con:
        con.execute("DELETE FROM vendor_sessions WHERE token = ?", (token,))


def get_vendor_by_token(token: str) -> Optional[dict]:
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as con:
        row = con.execute(
            """
            SELECT v.*, s.name AS supplier_name, s.district, s.upazila, s.phone, s.address
            FROM vendor_sessions vs
            JOIN vendor_accounts v ON v.id = vs.vendor_id
            LEFT JOIN suppliers s ON s.id = v.supplier_id
            WHERE vs.token = ? AND vs.expires_at > ?
            """,
            (token, now),
        ).fetchone()
    if not row or int(row["active"] or 0) != 1:
        return None
    item = _vendor_dict(row)
    item["supplier_name"] = row["supplier_name"] or ""
    item["district"] = row["district"] or ""
    item["upazila"] = row["upazila"] or ""
    item["phone"] = row["phone"] or ""
    item["address"] = row["address"] if "address" in row.keys() else ""
    return item


def vendor_stats(supplier_id: int) -> dict:
    with _connect() as con:
        orders = con.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE supplier_id = ?",
            (supplier_id,),
        ).fetchone()["c"]
        pending = con.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE supplier_id = ? AND status IN ('pending','confirmed','processing')",
            (supplier_id,),
        ).fetchone()["c"]
        revenue = con.execute(
            "SELECT COALESCE(SUM(total_bdt),0) AS s FROM orders WHERE supplier_id = ? AND status != 'cancelled'",
            (supplier_id,),
        ).fetchone()["s"]
        listings = con.execute(
            "SELECT COUNT(*) AS c FROM supplier_products WHERE supplier_id = ?",
            (supplier_id,),
        ).fetchone()["c"]
        low_stock = con.execute(
            "SELECT COUNT(*) AS c FROM supplier_products WHERE supplier_id = ? AND COALESCE(stock,0) <= 5",
            (supplier_id,),
        ).fetchone()["c"]
        by_status = {
            r["status"]: int(r["c"])
            for r in con.execute(
                "SELECT status, COUNT(*) AS c FROM orders WHERE supplier_id = ? GROUP BY status",
                (supplier_id,),
            ).fetchall()
        }
    return {
        "orders": int(orders),
        "orders_open": int(pending),
        "revenue_bdt": round(float(revenue or 0), 2),
        "listings": int(listings),
        "low_stock": int(low_stock),
        "orders_by_status": by_status,
    }
