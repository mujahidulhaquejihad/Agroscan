"""AgroScan API - serves the web app and the future mobile app.

Endpoints:
  GET  /api/status         -> which models are loaded, device
  GET  /api/classes        -> disease class list
  POST /api/predict        -> multipart image upload -> 3-level result JSON
The static web UI is served from / (the ../web folder).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agroscan.auth_store import (
    admin_delete_user,
    admin_get_user,
    admin_list_users,
    admin_revoke_user_sessions,
    admin_update_user,
    admin_user_stats,
    create_local_user,
    create_session,
    delete_session,
    get_user_by_token,
    init_db,
    login_local,
    update_user_profile,
    upsert_google_user,
)
from agroscan.image_io import load_rgb_image
from agroscan.infer import InferenceEngine
from agroscan.knowledge import (
    EMERGENCY_CONTACTS,
    GOV_LINKS,
    advice_for,
)
from agroscan.leaf_crop import auto_crop_leaf, image_to_jpeg_bytes, perspective_crop
from agroscan.llm_chat import chat_reply, llm_status, preload as llm_preload, transcribe_audio, vision_scan_reply
from agroscan.news import list_news
from agroscan.shop_db import (
    admin_shop_stats,
    assign_order_supplier,
    create_order,
    create_vendor,
    get_order,
    get_vendor_by_token,
    init_shop_db,
    list_orders,
    list_products,
    list_supplier_listings,
    list_suppliers,
    list_suppliers_admin,
    list_upazilas,
    list_vendors,
    nearest_upazila,
    product_with_suppliers,
    recommended_products_for_disease,
    reset_vendor_password,
    set_vendor_active,
    update_order,
    update_order_status,
    update_product_price,
    update_supplier_listing,
    update_supplier_profile,
    upsert_supplier_listing,
    vendor_self_update,
    update_vendor,
    vendor_login,
    vendor_logout,
    vendor_stats,
)

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

app = FastAPI(title="AgroScan", version="2.0.0")

# Allow the mobile app (and any web origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: InferenceEngine | None = None


def _optional_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return get_user_by_token(authorization[7:])


@app.on_event("startup")
def _load():
    global engine
    init_db()
    init_shop_db()
    try:
        from agroscan.shop_db import _connect
        from agroscan.shop_seed import seed_from_pack

        with _connect() as con:
            n = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            pest = con.execute("SELECT 1 FROM products WHERE sku LIKE 'PEST-%' LIMIT 1").fetchone()
        if n < 200 or not pest:
            print("Seeding shop from Bangladesh data pack:", seed_from_pack())
    except Exception as exc:
        print("Shop seed skipped:", exc)
    engine = InferenceEngine()
    print("Engine status:", engine.status())
    # Lazy by default: set AGROSCAN_LLM_PRELOAD=1 after closing browsers to warm GPU.
    if (os.environ.get("AGROSCAN_LLM_PRELOAD") or "").strip() in ("1", "true", "yes"):
        print("LLM status:", llm_preload())
    else:
        print("LLM status:", llm_status())


@app.get("/api/status")
def status():
    if engine is None:
        return {"ready": False, "message": "Server is still loading models..."}
    s = engine.status()
    s["ready"] = engine.ready
    s["llm"] = llm_status()
    return s


@app.post("/api/llm/load")
def llm_load():
    """Retry loading the local LLM (Gemma 9B). Call after freeing VRAM."""
    # Allow retry even if a previous pagefile error soft-disabled the LLM.
    import agroscan.llm_chat as lc

    lc._disabled = False
    lc._load_error = None
    return llm_preload()


@app.get("/api/classes")
def classes():
    return {"disease_classes": engine.disease_classes}


@app.post("/api/predict")
async def predict(
    file: UploadFile = File(...),
    crop: str | None = Form(default=None),
    land_size: float | None = Form(default=None),
    land_unit: str | None = Form(default="decimal"),
    lang: str | None = Form(default="bn"),
):
    if engine is None or not engine.ready:
        raise HTTPException(503, "Models are not trained/loaded yet.")
    data = await file.read()
    try:
        img = load_rgb_image(data, fallback_size=None)
    except Exception:
        raise HTTPException(400, "Could not read the uploaded image.")
    crop_override = (crop or "").strip() or None
    size = None
    if land_size is not None:
        try:
            size = float(land_size)
            if size <= 0:
                size = None
        except (TypeError, ValueError):
            size = None
    return engine.predict(
        img,
        crop_override=crop_override,
        land_size=size,
        land_unit=(land_unit or "decimal").strip() or "decimal",
        lang=(lang or "bn").strip() or "bn",
    )


class AutoCropIn(BaseModel):
    points: list[list[float]] | None = None


@app.post("/api/preprocess/auto-crop")
async def preprocess_auto_crop(
    file: UploadFile = File(...),
    isolate: bool = Form(False),
):
    data = await file.read()
    try:
        img = load_rgb_image(data, fallback_size=None)
    except Exception:
        raise HTTPException(400, "Could not read the uploaded image.")
    cropped, meta = auto_crop_leaf(img, isolate=bool(isolate))
    import json

    return Response(
        content=image_to_jpeg_bytes(cropped),
        media_type="image/jpeg",
        headers={"X-Crop-Meta": json.dumps(meta, ensure_ascii=False)},
    )


@app.post("/api/preprocess/perspective-crop")
async def preprocess_perspective_crop(
    file: UploadFile = File(...),
    points: str = Form(...),
):
    import json

    data = await file.read()
    try:
        img = load_rgb_image(data, fallback_size=None)
        pts = json.loads(points)
    except Exception:
        raise HTTPException(400, "Invalid image or crop points.")
    if not isinstance(pts, list) or len(pts) != 4:
        raise HTTPException(400, "Provide exactly 4 corner points [[x,y], ...].")
    cropped = perspective_crop(img, pts)
    return Response(content=image_to_jpeg_bytes(cropped), media_type="image/jpeg")


# --------------------------------------------------------------------------- #
# Chatbot, resources and advice (also consumable by the mobile app)
# --------------------------------------------------------------------------- #
class ChatTurn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    message: str
    context_disease: str | None = None
    lang: str | None = "bn"
    confirm_class: str | None = None
    district: str | None = None
    upazila: str | None = None
    lat: float | None = None
    lng: float | None = None
    history: list[ChatTurn] | None = None


@app.post("/api/chat/stt")
async def chat_stt(
    file: UploadFile = File(...),
    lang: str | None = Form(default="bn"),
):
    raw = await file.read()
    if not raw or len(raw) < 400:
        raise HTTPException(400, "Audio too short.")
    if len(raw) > 2_000_000:
        raise HTTPException(400, "Audio too long.")
    mime = (file.content_type or "audio/wav").split(";")[0].strip()
    text = transcribe_audio(raw, mime, lang or "bn")
    if not text:
        raise HTTPException(502, "Could not transcribe speech.")
    return {"text": text}


@app.post("/api/chat")
def chat(body: ChatIn):
    # Gemini + RAG when enabled; pack/KB fallback otherwise.
    loc = None
    if body.district or body.upazila or body.lat is not None:
        loc = {
            "district": body.district,
            "upazila": body.upazila,
            "lat": body.lat,
            "lng": body.lng,
        }
    hist = None
    if body.history:
        hist = [{"role": t.role, "content": t.content} for t in body.history]
    return chat_reply(
        body.message,
        body.context_disease,
        body.lang or "bn",
        confirm_class=body.confirm_class,
        location=loc,
        history=hist,
    )


@app.post("/api/chat/vision")
async def chat_vision(
    file: UploadFile = File(...),
    crop: str | None = Form(default=None),
    land_size: float | None = Form(default=None),
    land_unit: str | None = Form(default="decimal"),
    lang: str | None = Form(default="bn"),
):
    """Leaf photo → L1/L2/L3 vision models → Qwen farmer feedback."""
    if engine is None or not engine.ready:
        raise HTTPException(503, "Models are not trained/loaded yet.")
    data = await file.read()
    try:
        img = load_rgb_image(data, fallback_size=None)
    except Exception:
        raise HTTPException(400, "Could not read the uploaded image.")
    crop_override = (crop or "").strip() or None
    size = None
    if land_size is not None:
        try:
            size = float(land_size)
            if size <= 0:
                size = None
        except (TypeError, ValueError):
            size = None
    use_lang = (lang or "bn").strip() or "bn"
    pred = engine.predict(
        img,
        crop_override=crop_override,
        land_size=size,
        land_unit=(land_unit or "decimal").strip() or "decimal",
        lang=use_lang,
    )
    return vision_scan_reply(pred, use_lang)


@app.get("/api/resources")
def resources():
    return {"emergency_contacts": EMERGENCY_CONTACTS, "gov_links": GOV_LINKS}


@app.get("/api/news")
def news(lang: str = "bn", limit: int = 40):
    """Farmer advisories / latest news for the Notifications tab."""
    return list_news(lang=lang or "bn", limit=limit)


@app.get("/api/advice/{class_name}")
def advice(
    class_name: str,
    lang: str = "bn",
    land_size: float | None = None,
    land_unit: str = "decimal",
):
    size = land_size if land_size is not None and land_size > 0 else None
    info = advice_for(
        class_name,
        lang,
        land_size=size,
        land_unit=land_unit or "decimal",
    )
    if info is None:
        raise HTTPException(404, "No advice found for that class.")
    return info


@app.get("/api/diseases")
def diseases(lang: str = "bn"):
    from agroscan.knowledge import all_diseases

    return {"diseases": all_diseases(lang)}


class FarmPlanIn(BaseModel):
    district: str | None = ""
    land_size: float = 10.0
    land_unit: str | None = "decimal"  # decimal | bigha | acre
    season: str | None = None  # rabi | kharif1 | kharif2
    month: int | None = None
    temperature: float | None = None
    humidity: float | None = None
    soil_moisture: float | None = None
    lang: str | None = "bn"


@app.get("/api/crops")
def crops_catalog():
    from agroscan.farm_plan import load_flora_crops

    return {"crops": load_flora_crops()}


@app.post("/api/farm/plan")
def farm_plan(body: FarmPlanIn):
    from agroscan.farm_plan import recommend_crops

    return recommend_crops(
        district=body.district or "",
        land_size=float(body.land_size or 10),
        land_unit=body.land_unit or "decimal",
        season=body.season,
        month=body.month,
        temperature=body.temperature,
        humidity=body.humidity,
        soil_moisture=body.soil_moisture,
        lang=body.lang or "bn",
    )


@app.get("/api/farm/cultivate/{crop_name}")
def farm_cultivate(crop_name: str, lang: str = "bn"):
    from agroscan.farm_plan import cultivation_outline

    return cultivation_outline(crop_name, lang)


# --------------------------------------------------------------------------- #
# Shop: suppliers, products, orders (PostgreSQL recommended for production)
# --------------------------------------------------------------------------- #
class OrderItemIn(BaseModel):
    product_id: int
    qty: float = 1.0
    unit_price_bdt: float | None = None


class CreateOrderIn(BaseModel):
    items: list[OrderItemIn]
    user_name: str = ""
    user_phone: str = ""
    district: str = ""
    upazila: str = ""
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    supplier_id: int | None = None
    notes: str = ""
    user_id: int | None = None
    confirm: bool = False


class OrderStatusIn(BaseModel):
    status: str = ""
    message: str = ""
    supplier_id: int | None = None
    user_name: str | None = None
    user_phone: str | None = None
    district: str | None = None
    upazila: str | None = None
    address: str | None = None
    notes: str | None = None
    items: list[OrderItemIn] | None = None


class AdminLoginIn(BaseModel):
    username: str = "admin"
    password: str = ""


class VendorLoginIn(BaseModel):
    username: str = ""
    password: str = ""


class VendorIn(BaseModel):
    username: str
    password: str
    supplier_id: int


class VendorPatchIn(BaseModel):
    password: str | None = None
    active: int | None = None
    supplier_id: int | None = None
    username: str | None = None


class ListingPatchIn(BaseModel):
    price_bdt: float | None = None
    stock: int | None = None


class ListingCreateIn(BaseModel):
    product_id: int
    price_bdt: float | None = None
    stock: int | None = 0


class VendorMeIn(BaseModel):
    phone: str | None = None
    address: str | None = None
    password: str | None = None


@app.get("/api/shop/upazilas")
def shop_upazilas(district: str = ""):
    return {"upazilas": list_upazilas(district)}


@app.get("/api/shop/nearest-upazila")
def shop_nearest_upazila(lat: float, lng: float):
    hit = nearest_upazila(lat, lng)
    if not hit:
        raise HTTPException(404, "No upazila centroids available.")
    return {"upazila": hit}


@app.get("/api/shop/suppliers")
def shop_suppliers(
    district: str = "",
    upazila: str = "",
    limit: int = 10,
    lat: float | None = None,
    lng: float | None = None,
):
    return {
        "suppliers": list_suppliers(
            district, upazila, min(limit, 20), lat=lat, lng=lng
        )
    }


@app.get("/api/shop/products")
def shop_products(
    category: str = "",
    search: str = "",
    disease_key: str = "",
    crop: str = "",
    limit: int = 50,
    offset: int = 0,
):
    return {
        "products": list_products(category, search, disease_key, crop, min(limit, 100), offset)
    }


@app.get("/api/shop/products/{product_id}")
def shop_product(product_id: int, district: str = "", upazila: str = ""):
    p = product_with_suppliers(product_id, district, upazila)
    if not p:
        raise HTTPException(404, "Product not found.")
    return p


@app.get("/api/shop/recommend")
def shop_recommend(disease_class: str, district: str = "", upazila: str = ""):
    return {"products": recommended_products_for_disease(disease_class, district, upazila)}


@app.post("/api/shop/orders")
def shop_create_order(body: CreateOrderIn, user=Depends(_optional_user)):
    try:
        order = create_order(
            items=[it.model_dump() for it in body.items],
            user_id=user["id"] if user else None,
            user_name=body.user_name or (user["name"] if user else ""),
            user_phone=body.user_phone,
            district=body.district,
            upazila=body.upazila,
            address=body.address,
            lat=body.lat,
            lng=body.lng,
            supplier_id=body.supplier_id,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "order": order}


@app.get("/api/shop/orders")
def shop_orders(user=Depends(_optional_user), status: str = ""):
    if not user:
        raise HTTPException(401, "Sign in to view orders.")
    return {"orders": list_orders(user_id=user["id"], status=status)}


@app.get("/api/shop/orders/{order_code}")
def shop_order_detail(order_code: str, user=Depends(_optional_user)):
    try:
        order = get_order(order_code)
    except ValueError:
        raise HTTPException(404, "Order not found.")
    if user and order.get("user_id") and order["user_id"] != user["id"]:
        raise HTTPException(403, "Not your order.")
    return order


DEFAULT_ADMIN_TOKEN = "agroscan-admin"


def _admin_expected_token() -> str:
    return (os.environ.get("AGROSCAN_ADMIN_TOKEN") or DEFAULT_ADMIN_TOKEN).strip()


def _admin_expected_user() -> str:
    return (os.environ.get("AGROSCAN_ADMIN_USER") or "admin").strip() or "admin"


def _admin_token_ok(authorization: str | None = Header(default=None)) -> bool:
    expected = _admin_expected_token()
    if not expected:
        return False
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return authorization[7:] == expected


def _vendor_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Vendor sign-in required.")
    vendor = get_vendor_by_token(authorization[7:])
    if not vendor:
        raise HTTPException(401, "Vendor sign-in required.")
    return vendor


@app.post("/api/admin/login")
def admin_login(body: AdminLoginIn):
    user = (body.username or "").strip()
    password = body.password or ""
    if user != _admin_expected_user() or password != _admin_expected_token():
        raise HTTPException(401, "Wrong username or password.")
    return {"ok": True, "token": password, "role": "admin"}


@app.get("/api/admin/orders")
def admin_orders(
    status: str = "",
    search: str = "",
    unassigned: bool = False,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    return {
        "orders": list_orders(
            status=status, search=search, unassigned=unassigned, limit=200
        )
    }


@app.get("/api/admin/orders/{order_code}")
def admin_order_detail(order_code: str, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        return get_order(order_code)
    except ValueError:
        raise HTTPException(404, "Order not found.")


@app.get("/api/admin/stats")
def admin_stats(authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    shop = admin_shop_stats()
    users = admin_user_stats()
    try:
        models = {
            "llm": llm_status(),
            "vision": {
                "loaded": engine is not None,
                "device": getattr(engine, "device", None) if engine else None,
            },
        }
    except Exception:
        models = {"llm": {"ok": False}, "vision": {"loaded": False}}
    return {"shop": shop, "users": users, "models": models}


@app.get("/api/admin/users")
def admin_users(
    search: str = "",
    limit: int = 100,
    offset: int = 0,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    return admin_list_users(search=search, limit=limit, offset=offset)


@app.get("/api/admin/users/{user_id}")
def admin_user_detail(user_id: int, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        return {"user": admin_get_user(user_id)}
    except ValueError as e:
        raise HTTPException(404, str(e))


class AdminUserIn(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    district: str | None = None
    upazila: str | None = None
    active: int | None = None
    password: str | None = None


@app.patch("/api/admin/users/{user_id}")
def admin_user_update(
    user_id: int,
    body: AdminUserIn,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        user = admin_update_user(
            user_id,
            name=body.name,
            email=body.email,
            phone=body.phone,
            address=body.address,
            district=body.district,
            upazila=body.upazila,
            active=body.active,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "user": user}


@app.post("/api/admin/users")
def admin_user_create(body: AdminUserIn, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    name = (body.name or "").strip()
    email = (body.email or "").strip()
    password = (body.password or "").strip()
    if not name or not email or len(password) < 6:
        raise HTTPException(400, "Name, email, and a password of at least 6 characters are required.")
    try:
        user = create_local_user(
            name,
            email,
            password,
            phone=body.phone or "",
            address=body.address or "",
            district=body.district or "",
            upazila=body.upazila or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "user": user}


@app.post("/api/admin/users/{user_id}/revoke-sessions")
def admin_user_revoke(user_id: int, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    n = admin_revoke_user_sessions(user_id)
    return {"ok": True, "revoked": n}


@app.delete("/api/admin/users/{user_id}")
def admin_user_delete(user_id: int, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        admin_delete_user(user_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@app.patch("/api/admin/orders/{order_code}")
def admin_update_order(
    order_code: str,
    body: OrderStatusIn,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        if (
            body.user_name is not None
            or body.user_phone is not None
            or body.district is not None
            or body.upazila is not None
            or body.address is not None
            or body.notes is not None
            or body.items is not None
            or body.supplier_id is not None
        ):
            update_order(
                order_code,
                user_name=body.user_name,
                user_phone=body.user_phone,
                district=body.district,
                upazila=body.upazila,
                address=body.address,
                notes=body.notes,
                supplier_id=body.supplier_id,
                items=[it.model_dump() for it in body.items] if body.items is not None else None,
                actor="admin",
            )
        if body.status:
            order = update_order_status(order_code, body.status, body.message, "admin")
        else:
            order = get_order(order_code)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "order": order}


@app.post("/api/admin/orders")
def admin_create_order(body: CreateOrderIn, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        order = create_order(
            items=[it.model_dump() for it in body.items],
            user_id=body.user_id,
            user_name=body.user_name,
            user_phone=body.user_phone,
            district=body.district,
            upazila=body.upazila,
            address=body.address,
            lat=body.lat,
            lng=body.lng,
            supplier_id=body.supplier_id,
            notes=body.notes,
            actor="admin",
        )
        if body.confirm:
            order = update_order_status(order["order_code"], "confirmed", "Confirmed by admin", "admin")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "order": order}


@app.post("/api/admin/seed")
def admin_seed(authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    from agroscan.shop_seed import seed_from_pack

    return seed_from_pack()


@app.post("/api/admin/apply-images")
def admin_apply_images(authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    from agroscan.shop_seed import apply_product_images

    return apply_product_images()

@app.get("/api/admin/products")
def admin_products(
    search: str = "",
    category: str = "",
    limit: int = 100,
    offset: int = 0,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    return {
        "products": list_products(
            category=category, search=search, limit=min(limit, 300), offset=offset
        )
    }


def _apply_admin_product_price(product_id: int, price_bdt: float) -> dict:
    try:
        return update_product_price(product_id, price_bdt)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/admin/products/{product_id}/price")
def admin_set_product_price(
    product_id: int,
    price_bdt: float,
    authorization: str | None = Header(default=None),
):
    """Set fixed shop price (query param — avoids JSON body parse issues)."""
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    product = _apply_admin_product_price(product_id, price_bdt)
    return {"ok": True, "product": product}


@app.patch("/api/admin/products/{product_id}")
async def admin_update_product_price(
    product_id: int,
    request: Request,
    authorization: str | None = Header(default=None),
    price_bdt: float | None = None,
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    value = price_bdt
    if value is None:
        raw = await request.body()
        if raw:
            try:
                import json as _json

                payload = _json.loads(raw)
            except Exception:
                raise HTTPException(
                    400,
                    "Invalid JSON body. Use ?price_bdt=123 or JSON {\"price_bdt\": 123}.",
                )
            if not isinstance(payload, dict) or payload.get("price_bdt") is None:
                raise HTTPException(400, "price_bdt is required.")
            value = float(payload["price_bdt"])
    if value is None:
        raise HTTPException(400, "price_bdt is required.")
    product = _apply_admin_product_price(product_id, value)
    return {"ok": True, "product": product}


@app.get("/api/admin/suppliers")
def admin_suppliers(
    search: str = "",
    limit: int = 80,
    offset: int = 0,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    return list_suppliers_admin(search=search, limit=limit, offset=offset)


@app.get("/api/admin/vendors")
def admin_vendors_list(authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    return {"vendors": list_vendors()}


@app.post("/api/admin/vendors")
def admin_vendors_create(body: VendorIn, authorization: str | None = Header(default=None)):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        vendor = create_vendor(body.username, body.password, body.supplier_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "vendor": vendor}


@app.patch("/api/admin/vendors/{vendor_id}")
def admin_vendors_patch(
    vendor_id: int,
    body: VendorPatchIn,
    authorization: str | None = Header(default=None),
):
    if not _admin_token_ok(authorization):
        raise HTTPException(401, "Admin token required.")
    try:
        vendor = update_vendor(
            vendor_id,
            username=body.username,
            supplier_id=body.supplier_id,
            password=body.password,
            active=body.active,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "vendor": vendor}


@app.post("/api/vendor/login")
def vendor_login_api(body: VendorLoginIn):
    try:
        return vendor_login(body.username, body.password)
    except ValueError as e:
        raise HTTPException(401, str(e))


@app.post("/api/vendor/logout")
def vendor_logout_api(vendor=Depends(_vendor_user), authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        vendor_logout(authorization[7:])
    return {"ok": True}


@app.get("/api/vendor/me")
def vendor_me(vendor=Depends(_vendor_user)):
    return {"vendor": vendor}


@app.patch("/api/vendor/me")
def vendor_me_patch(
    body: VendorMeIn,
    vendor=Depends(_vendor_user),
    authorization: str | None = Header(default=None),
):
    try:
        if body.phone is not None or body.address is not None:
            update_supplier_profile(
                vendor["supplier_id"],
                phone=body.phone,
                address=body.address,
            )
        if body.password:
            keep = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
            vendor_self_update(vendor["id"], password=body.password, keep_token=keep)
        fresh = get_vendor_by_token(
            authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "vendor": fresh or vendor}


@app.get("/api/vendor/stats")
def vendor_stats_api(vendor=Depends(_vendor_user)):
    return {"vendor": vendor, "shop": vendor_stats(vendor["supplier_id"])}


@app.get("/api/vendor/orders")
def vendor_orders_api(
    status: str = "",
    search: str = "",
    vendor=Depends(_vendor_user),
):
    return {
        "orders": list_orders(
            supplier_id=vendor["supplier_id"],
            status=status,
            search=search,
            limit=200,
        )
    }


@app.get("/api/vendor/orders/{order_code}")
def vendor_order_detail(order_code: str, vendor=Depends(_vendor_user)):
    try:
        order = get_order(order_code)
    except ValueError:
        raise HTTPException(404, "Order not found.")
    if int(order.get("supplier_id") or 0) != int(vendor["supplier_id"]):
        raise HTTPException(403, "Not your order.")
    return order


@app.patch("/api/vendor/orders/{order_code}")
def vendor_update_order(order_code: str, body: OrderStatusIn, vendor=Depends(_vendor_user)):
    if not body.status:
        raise HTTPException(400, "status is required.")
    try:
        order = update_order_status(
            order_code,
            body.status,
            body.message or "Updated by vendor",
            f"vendor:{vendor['username']}",
            supplier_id=vendor["supplier_id"],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "order": order}


@app.get("/api/vendor/listings")
def vendor_listings(
    search: str = "",
    limit: int = 80,
    offset: int = 0,
    low_stock: bool = False,
    vendor=Depends(_vendor_user),
):
    return list_supplier_listings(
        vendor["supplier_id"],
        search=search,
        limit=min(limit, 300),
        offset=offset,
        low_stock=low_stock,
    )


@app.post("/api/vendor/listings")
def vendor_listing_create(body: ListingCreateIn, vendor=Depends(_vendor_user)):
    try:
        item = upsert_supplier_listing(
            vendor["supplier_id"],
            body.product_id,
            price_bdt=body.price_bdt,
            stock=body.stock,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "product": item}


@app.patch("/api/vendor/listings/{product_id}")
def vendor_listing_patch(product_id: int, body: ListingPatchIn, vendor=Depends(_vendor_user)):
    try:
        item = update_supplier_listing(
            vendor["supplier_id"],
            product_id,
            price_bdt=body.price_bdt,
            stock=body.stock,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "product": item}


@app.get("/api/safety")
def safety_ref(lang: str = "bn"):
    from agroscan.bd_data import safety

    pack = safety()
    return {
        "topics": pack.get("topics") or [],
        "ui_warning_boxes": pack.get("ui_warning_boxes") or [],
        "helplines": pack.get("helplines") or [],
        "official_portals": pack.get("official_portals") or [],
        "lang": lang,
    }


# --------------------------------------------------------------------------- #
# Auth: signup, login, logout, Google, session
# --------------------------------------------------------------------------- #
class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    phone: str = ""
    address: str = ""
    district: str = ""
    upazila: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class GoogleAuthIn(BaseModel):
    id_token: str
    client_id: str


def _auth_response(user: dict) -> dict:
    token = create_session(user["id"])
    return {"ok": True, "token": token, "user": user}


@app.post("/api/auth/signup")
def auth_signup(body: SignupIn):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    try:
        user = create_local_user(
            body.name,
            body.email,
            body.password,
            phone=body.phone,
            address=body.address,
            district=body.district,
            upazila=body.upazila,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _auth_response(user)


@app.post("/api/auth/login")
def auth_login(body: LoginIn):
    try:
        user = login_local(body.email, body.password)
    except ValueError:
        raise HTTPException(401, "Invalid email or password.")
    return _auth_response(user)


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        delete_session(authorization[7:])
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(user=Depends(_optional_user)):
    if not user:
        raise HTTPException(401, "Not signed in.")
    return {"user": user}


class ProfileIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    district: str | None = None
    upazila: str | None = None


@app.patch("/api/auth/profile")
def auth_profile(body: ProfileIn, user=Depends(_optional_user)):
    if not user:
        raise HTTPException(401, "Not signed in.")
    try:
        updated = update_user_profile(
            user["id"],
            name=body.name,
            phone=body.phone,
            address=body.address,
            district=body.district,
            upazila=body.upazila,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "user": updated}


@app.post("/api/auth/google")
def auth_google(body: GoogleAuthIn):
    try:
        from google.oauth2 import id_token as gid_token
        from google.auth.transport import requests as g_requests
    except Exception:
        raise HTTPException(
            501,
            "Server-side Google verification needs `pip install google-auth`.",
        )
    try:
        info = gid_token.verify_oauth2_token(
            body.id_token, g_requests.Request(), body.client_id
        )
    except Exception:
        raise HTTPException(401, "Invalid Google token.")
    user = upsert_google_user(
        info.get("name") or "Google User",
        info.get("email") or "",
        info.get("picture") or "",
        info.get("sub") or "",
    )
    return _auth_response(user)


# --------------------------------------------------------------------------- #
# Static web UI
# --------------------------------------------------------------------------- #
if WEB_DIR.exists():
    @app.get("/sw.js")
    def service_worker():
        # Must be served from site root so the SW scope can cover "/"
        return FileResponse(
            str(WEB_DIR / "sw.js"),
            media_type="application/javascript; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Service-Worker-Allowed": "/",
            },
        )

    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(WEB_DIR / "index.html"))

    @app.get("/index.html")
    def index_html():
        return index()

    @app.get("/login")
    def login_page():
        return FileResponse(str(WEB_DIR / "login.html"))

    @app.get("/login.html")
    def login_html():
        return login_page()

    @app.get("/signup")
    def signup_page():
        return FileResponse(str(WEB_DIR / "signup.html"))

    @app.get("/signup.html")
    def signup_html():
        return signup_page()

    @app.get("/logout")
    def logout_page():
        return FileResponse(str(WEB_DIR / "logout.html"))

    @app.get("/logout.html")
    def logout_html():
        return logout_page()

    @app.get("/account")
    def account_page():
        return FileResponse(str(WEB_DIR / "account.html"))

    @app.get("/account.html")
    def account_html():
        return account_page()

    @app.get("/admin")
    def admin_page():
        return FileResponse(
            str(WEB_DIR / "admin.html"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/admin.html")
    def admin_html():
        return admin_page()

    @app.get("/vendor")
    def vendor_page():
        return FileResponse(
            str(WEB_DIR / "vendor.html"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/vendor.html")
    def vendor_html():
        return vendor_page()
