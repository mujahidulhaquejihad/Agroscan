"""Vendor accounts, auto-assign supplier, stock decrement."""
from pathlib import Path
import tempfile

import agroscan.shop_db as shop_db

shop_db.SHOP_DB_PATH = Path(tempfile.mkdtemp()) / "shop.db"
shop_db.init_shop_db()

got = shop_db.vendor_login("vendor", "agroscan-vendor")
assert got.get("token"), got
assert got["vendor"]["username"] == "vendor"
assert got["vendor"]["supplier_id"]

sid = got["vendor"]["supplier_id"]
now = shop_db._now()
with shop_db._connect() as con:
    cur = con.execute(
        """
        INSERT INTO products (sku, name, category, price_bdt, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("TEST-UREA", "Test Urea", "fertilizer", 100, now),
    )
    pid = int(cur.lastrowid)
    con.execute(
        """
        INSERT INTO supplier_products (supplier_id, product_id, price_bdt, stock)
        VALUES (?, ?, ?, ?)
        """,
        (sid, pid, 100, 10),
    )

order = shop_db.create_order(
    items=[{"product_id": pid, "qty": 2}],
    user_name="Farmer",
    user_phone="01700000000",
    district="Dhaka",
    upazila="Dhaka South",
    address="Test road",
)
assert order["supplier_id"] == sid, order
assert order["total_bdt"] == 200, order

listings = shop_db.list_supplier_listings(sid)["products"]
assert listings and listings[0]["stock"] == 8, listings

shop = shop_db.update_supplier_profile(sid, phone="01711", address="New road")
assert shop["phone"] == "01711"
pid2 = None
with shop_db._connect() as con:
    cur = con.execute(
        "INSERT INTO products (sku, name, category, price_bdt, created_at) VALUES (?,?,?,?,?)",
        ("TEST-DAP", "Test DAP", "fertilizer", 80, now),
    )
    pid2 = int(cur.lastrowid)
added = shop_db.upsert_supplier_listing(sid, pid2, price_bdt=90, stock=4)
assert added["stock"] == 4
low = shop_db.list_supplier_listings(sid, low_stock=True)["products"]
assert any(p["id"] == pid2 for p in low)

me = shop_db.get_vendor_by_token(got["token"])
assert me and me["id"] == got["vendor"]["id"]

try:
    shop_db.vendor_login("vendor", "wrong-pass")
    raise SystemExit("bad password should fail")
except ValueError:
    pass

print("ok", order["order_code"], "stock=8")
