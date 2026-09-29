"""Admin can add/edit users, vendors, orders, and confirm orders."""
from pathlib import Path
import tempfile

import agroscan.auth_store as auth
import agroscan.shop_db as shop_db

tmp = Path(tempfile.mkdtemp())
auth.DB_PATH = tmp / "users.db"
shop_db.SHOP_DB_PATH = tmp / "shop.db"
auth.init_db()
shop_db.init_shop_db()

user = auth.create_local_user("Farmer One", "farmer@test.com", "secret1", phone="01711")
assert user["id"] and user["email"] == "farmer@test.com"
edited = auth.admin_update_user(user["id"], name="Farmer Two", phone="01712")
assert edited["name"] == "Farmer Two"

v = shop_db.create_vendor("dhaka_shop", "secret1", shop_db.list_vendors()[0]["supplier_id"])
sid2 = shop_db.list_suppliers_admin(limit=5)["suppliers"][0]["id"]
v2 = shop_db.update_vendor(v["id"], username="dhaka_shop2", supplier_id=sid2)
assert v2["username"] == "dhaka_shop2"

now = shop_db._now()
with shop_db._connect() as con:
    cur = con.execute(
        "INSERT INTO products (sku, name, category, price_bdt, created_at) VALUES (?,?,?,?,?)",
        ("TEST-SEED", "Test Seed", "seed", 50, now),
    )
    pid = int(cur.lastrowid)

order = shop_db.create_order(
    items=[{"product_id": pid, "qty": 2}],
    user_name="Farmer Two",
    user_phone="01712",
    district="Dhaka",
    upazila="Savar",
    address="Road 1",
    actor="admin",
)
assert order["status"] == "pending"
assert order["total_bdt"] == 100

order = shop_db.update_order(
    order["order_code"],
    user_name="Farmer Two",
    address="Road 2",
    items=[{"product_id": pid, "qty": 3}],
)
assert order["address"] == "Road 2"
assert order["total_bdt"] == 150

order = shop_db.update_order_status(order["order_code"], "confirmed", "ok", "admin")
assert order["status"] == "confirmed"
print("ok", order["order_code"])
