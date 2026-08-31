"""
Generate unique shop product images (packaging-style cards) + short descriptions.
Does not depend on flaky external image hosts.

Writes:
  web/shop-images/{SKU}.jpg
  data/agroscan/product_images.json
  data/agroscan/product_short_descriptions.json
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "agroscan"
OUT = ROOT / "web" / "shop-images"
MAP_PATH = PACK / "product_images.json"
DESC_PATH = PACK / "product_short_descriptions.json"

# Distinct palettes — avoid flat green-only look
PALETTES = {
    "fungicide": ((36, 99, 160), (14, 55, 110), (232, 242, 255), (255, 196, 61)),
    "insecticide": ((180, 83, 9), (120, 45, 8), (255, 243, 224), (254, 215, 170)),
    "herbicide": ((194, 65, 12), (124, 45, 18), (255, 247, 237), (253, 186, 116)),
    "fertilizer": ((146, 64, 14), (92, 38, 8), (254, 243, 199), (251, 191, 36)),
    "seed": ((161, 98, 7), (113, 63, 18), (254, 249, 195), (250, 204, 21)),
    "sprayer": ((71, 85, 105), (30, 41, 59), (241, 245, 249), (148, 163, 184)),
    "irrigation": ((8, 145, 178), (14, 116, 144), (236, 254, 255), (103, 232, 249)),
    "tool": ((87, 83, 78), (41, 37, 36), (245, 245, 244), (168, 162, 158)),
    "machine": ((55, 65, 81), (17, 24, 39), (243, 244, 246), (156, 163, 175)),
    "protective": ((190, 24, 93), (131, 24, 67), (253, 242, 248), (251, 113, 133)),
    "trap": ((202, 138, 4), (133, 77, 14), (254, 252, 232), (250, 204, 21)),
    "growth": ((5, 150, 105), (6, 95, 70), (236, 253, 245), (52, 211, 153)),
    "nematicide": ((180, 83, 9), (120, 53, 15), (255, 247, 237), (253, 186, 116)),
    "rodenticide": ((127, 29, 29), (69, 10, 10), (254, 242, 242), (252, 165, 165)),
    "acaricide": ((217, 119, 6), (146, 64, 14), (255, 251, 235), (253, 186, 116)),
    "equipment": ((75, 85, 99), (31, 41, 55), (249, 250, 251), (156, 163, 175)),
    "pesticide": ((30, 64, 175), (30, 58, 138), (239, 246, 255), (96, 165, 250)),
    "default": ((30, 64, 175), (30, 58, 138), (239, 246, 255), (96, 165, 250)),
}


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 3) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(1, len(lines[-1]) - 1)] + "…"
    return lines


def short_desc(row: dict) -> str:
    for key in (
        "usage_summary_en",
        "description_en",
        "typical_use_en",
        "specs_en",
        "usage_summary_bn",
        "description_bn",
    ):
        val = (row.get(key) or "").strip()
        if val:
            val = re.sub(r"\s+", " ", val)
            if len(val) > 140:
                val = val[:137].rstrip(" ,.;") + "…"
            return val
    name = row.get("name_en") or row.get("name") or "Product"
    sub = row.get("subcategory") or row.get("category") or "farm"
    brand = row.get("brand") or ""
    pack = row.get("pack_size") or row.get("unit") or ""
    bits = [f"{sub.capitalize()} for farm use."]
    if brand:
        bits.append(f"Brand: {brand}.")
    if pack:
        bits.append(f"Pack: {pack}.")
    bits.append(name)
    text = " ".join(bits)
    return text[:140]


def palette_for(row: dict) -> tuple:
    sub = (row.get("subcategory") or "").lower()
    cat = (row.get("category") or "").lower()
    if sub in PALETTES:
        return PALETTES[sub]
    if cat in PALETTES:
        return PALETTES[cat]
    # hash-based variation so siblings differ slightly
    h = int(hashlib.sha1((row.get("sku") or row.get("name_en") or "x").encode()).hexdigest()[:6], 16)
    base = PALETTES["default"]
    shift = ((h & 40) - 20, ((h >> 8) & 40) - 20, ((h >> 16) & 40) - 20)
    def adj(c):
        return tuple(max(0, min(255, c[i] + shift[i])) for i in range(3))
    return (adj(base[0]), adj(base[1]), base[2], base[3])


def draw_pack(draw: ImageDraw.ImageDraw, kind: str, box, fill, accent):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if kind in ("sprayer", "irrigation", "machine", "tool", "equipment"):
        # equipment block
        draw.rounded_rectangle(box, radius=18, fill=fill, outline=accent, width=3)
        draw.ellipse((x0 + w * 0.2, y0 + h * 0.15, x0 + w * 0.8, y0 + h * 0.55), fill=accent)
        draw.rectangle((x0 + w * 0.35, y0 + h * 0.5, x0 + w * 0.65, y0 + h * 0.85), fill=accent)
    elif kind in ("seed", "fertilizer"):
        # sack
        draw.polygon(
            [
                (x0 + w * 0.18, y0 + h * 0.22),
                (x0 + w * 0.82, y0 + h * 0.22),
                (x0 + w * 0.92, y0 + h * 0.88),
                (x0 + w * 0.08, y0 + h * 0.88),
            ],
            fill=fill,
            outline=accent,
        )
        draw.rectangle((x0 + w * 0.22, y0 + h * 0.12, x0 + w * 0.78, y0 + h * 0.28), fill=accent)
    else:
        # bottle / canister
        neck = [
            (x0 + w * 0.38, y0 + h * 0.08),
            (x0 + w * 0.62, y0 + h * 0.08),
            (x0 + w * 0.62, y0 + h * 0.22),
            (x0 + w * 0.38, y0 + h * 0.22),
        ]
        draw.rounded_rectangle(
            (x0 + w * 0.22, y0 + h * 0.2, x0 + w * 0.78, y0 + h * 0.92),
            radius=22,
            fill=fill,
            outline=accent,
            width=3,
        )
        draw.polygon(neck, fill=accent)
        draw.rectangle((x0 + w * 0.34, y0 + h * 0.02, x0 + w * 0.66, y0 + h * 0.1), fill=accent)


def render_card(row: dict) -> Image.Image:
    W, H = 720, 540
    primary, deep, light, accent = palette_for(row)
    sku = row.get("sku") or "SKU"
    h = int(hashlib.sha1(sku.encode()).hexdigest()[:8], 16)

    # Fast gradient background (not flat green)
    img = Image.new("RGB", (W, H), deep)
    top = Image.new("RGB", (W, H), primary)
    try:
        mask = Image.linear_gradient("L").resize((W, H))
        img = Image.composite(top, img, mask)
    except Exception:
        img = top
    img = img.convert("RGBA")
    draw_bg = ImageDraw.Draw(img, "RGBA")
    draw_bg.ellipse((-100 + (h % 40), -140, 380, 300), fill=(*light, 70))
    draw_bg.ellipse((360, 220, 820, 680), fill=(*accent, 45))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    kind = (row.get("subcategory") or row.get("category") or "pesticide").lower()
    pack_fill = (*primary, 235)
    pack_accent = (*accent, 255)
    draw_pack(d, kind, (70, 70, 320, 460), pack_fill, pack_accent)

    # label panel
    d.rounded_rectangle((340, 70, 680, 470), radius=28, fill=(255, 255, 255, 235))
    d.rounded_rectangle((360, 90, 520, 126), radius=10, fill=(*primary, 255))

    card = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(card)
    font_cat = load_font(18)
    font_title = load_font(28)
    font_meta = load_font(18)
    font_small = load_font(15)

    cat = (row.get("subcategory") or row.get("category") or "item").upper()
    draw.text((372, 96), cat[:16], font=font_cat, fill=(255, 255, 255))

    name = row.get("name_en") or row.get("name") or sku
    lines = wrap(draw, name, font_title, 300, 3)
    y = 150
    for line in lines:
        draw.text((360, y), line, font=font_title, fill=deep)
        y += 34

    brand = (row.get("brand") or "").strip()
    pack = (row.get("pack_size") or row.get("unit") or "").strip()
    ai = (row.get("active_ingredient") or "").strip()
    meta_y = y + 12
    if brand:
        draw.text((360, meta_y), brand[:36], font=font_meta, fill=primary)
        meta_y += 28
    if ai:
        draw.text((360, meta_y), ai[:40], font=font_small, fill=(80, 80, 90))
        meta_y += 24
    if pack:
        pw = int(draw.textlength(pack, font=font_small))
        draw.rounded_rectangle((360, meta_y, 378 + pw, meta_y + 28), radius=8, fill=accent)
        draw.text((368, meta_y + 4), pack, font=font_small, fill=deep)

    draw.text((360, 430), sku, font=font_small, fill=(120, 120, 130))
    return card.convert("RGB")


def load_rows() -> list[dict]:
    rows = []
    for fname, source in (("products.json", "product"), ("equipment.json", "equipment")):
        data = json.loads((PACK / fname).read_text(encoding="utf-8"))
        for row in data:
            row = dict(row)
            row["_source"] = source
            if source == "equipment":
                row.setdefault("category", "equipment")
            rows.append(row)
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    mapping = {}
    descs = {}
    print(f"Rendering {len(rows)} product images…", flush=True)
    for i, row in enumerate(rows, 1):
        sku = str(row.get("sku") or f"ITEM-{i}")
        card = render_card(row)
        path = OUT / f"{sku}.jpg"
        card.save(path, "JPEG", quality=88, optimize=True)
        mapping[sku] = {
            "path": f"/static/shop-images/{sku}.jpg",
            "query": "generated-packshot",
            "title": row.get("name_en") or sku,
            "license": "generated",
            "source_url": "",
            "creator": "AgroScan",
        }
        descs[sku] = short_desc(row)
        if i % 50 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)}", flush=True)
    MAP_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    DESC_PATH.write_text(json.dumps(descs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {MAP_PATH.name} + {DESC_PATH.name} + {len(list(OUT.glob('*.jpg')))} jpgs", flush=True)


if __name__ == "__main__":
    main()
