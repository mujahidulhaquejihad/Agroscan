"""Build centered AgroScan launcher, splash, and PWA icons from the brand PNG.

Run from repo root: python scripts/make_app_icons.py
Also invoked by mobile/scripts/patch-android.js before assembleDebug.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "AgroScan_logo-main.png"
WEB_ICONS = ROOT / "web" / "icons"
ANDROID_RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"

# Brand green used as the app chrome / theme_color.
BG = (4, 28, 18, 255)  # #041c12
LAUNCHER = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}
FOREGROUND = {
    "mdpi": 108,
    "hdpi": 162,
    "xhdpi": 216,
    "xxhdpi": 324,
    "xxxhdpi": 432,
}
PORT = {
    "mdpi": (320, 480),
    "hdpi": (480, 800),
    "xhdpi": (720, 1280),
    "xxhdpi": (960, 1600),
    "xxxhdpi": (1280, 1920),
}
LAND = {
    "mdpi": (480, 320),
    "hdpi": (800, 480),
    "xhdpi": (1280, 720),
    "xxhdpi": (1600, 960),
    "xxxhdpi": (1920, 1280),
}


def _key_black(im: Image.Image) -> Image.Image:
    """Turn near-black pixels transparent so the mark sits on the green canvas."""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
            if r < 36 and g < 36 and b < 36:
                px[x, y] = (r, g, b, 0)
    return im


def _trim(im: Image.Image) -> Image.Image:
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def _paste_centered(canvas: Image.Image, mark: Image.Image, width_frac: float) -> Image.Image:
    cw, ch = canvas.size
    target_w = max(1, int(cw * width_frac))
    ratio = target_w / mark.size[0]
    tw = target_w
    th = max(1, int(mark.size[1] * ratio))
    if th > int(ch * 0.72):
        th = max(1, int(ch * 0.72))
        tw = max(1, int(mark.size[0] * (th / mark.size[1])))
    scaled = mark.resize((tw, th), Image.Resampling.LANCZOS)
    x = (cw - tw) // 2
    y = (ch - th) // 2
    canvas.alpha_composite(scaled, (x, y))
    return canvas


def _square(mark: Image.Image, size: int, width_frac: float, transparent: bool) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0) if transparent else BG)
    if not transparent:
        canvas.paste(BG, (0, 0, size, size))
    return _paste_centered(canvas, mark, width_frac)


def _save(im: Image.Image, path: Path, rgb: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = im.convert("RGB") if rgb else im
    out.save(path, "PNG", optimize=True)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing logo: {SRC}")
    mark = _trim(_key_black(Image.open(SRC)))

    WEB_ICONS.mkdir(parents=True, exist_ok=True)
    _save(_square(mark, 192, 0.78, False), WEB_ICONS / "icon-192.png")
    _save(_square(mark, 512, 0.78, False), WEB_ICONS / "icon-512.png")

    if not ANDROID_RES.exists():
        print("No android/ res dir yet; wrote PWA icons only.")
        return

    for dens, size in LAUNCHER.items():
        icon = _square(mark, size, 0.78, False)
        folder = ANDROID_RES / f"mipmap-{dens}"
        _save(icon, folder / "ic_launcher.png")
        _save(icon, folder / "ic_launcher_round.png")

    for dens, size in FOREGROUND.items():
        # Adaptive safe zone is the inner ~66%; keep the wordmark inside it.
        fg = _square(mark, size, 0.56, True)
        _save(fg, ANDROID_RES / f"mipmap-{dens}" / "ic_launcher_foreground.png")

    bg_xml = """<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#041C12"
        android:pathData="M0,0h108v108h-108z" />
</vector>
"""
    (ANDROID_RES / "drawable" / "ic_launcher_background.xml").write_text(bg_xml, encoding="utf-8")
    (ANDROID_RES / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        '    <color name="ic_launcher_background">#041C12</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )

    for dens, (w, h) in PORT.items():
        canvas = Image.new("RGBA", (w, h), BG)
        _paste_centered(canvas, mark, 0.62)
        _save(canvas, ANDROID_RES / f"drawable-port-{dens}" / "splash.png", rgb=True)
    for dens, (w, h) in LAND.items():
        canvas = Image.new("RGBA", (w, h), BG)
        _paste_centered(canvas, mark, 0.42)
        _save(canvas, ANDROID_RES / f"drawable-land-{dens}" / "splash.png", rgb=True)
    fallback = Image.new("RGBA", (480, 320), BG)
    _paste_centered(fallback, mark, 0.5)
    _save(fallback, ANDROID_RES / "drawable" / "splash.png", rgb=True)

    print("ok icons ->", WEB_ICONS, "and", ANDROID_RES)


if __name__ == "__main__":
    main()
