"""Search Google Images, send each result to /api/predict exactly like the web app, save a report.

    python -m scripts.check_internet_images                      # live site, 100 images
    python -m scripts.check_internet_images --api http://127.0.0.1:8000 --per-query 10

The image list is frozen in internet_test/search.json and answers are cached per server in
internet_test/answers/<host>/. After a deploy, delete that server's answers folder and re-run.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "internet_test"
QUERIES = ("disease plants", "disease leaves", "leaves", "plant leaf disease", "crop disease leaf")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
EDGE = (
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
)


def google_images(query: str) -> list[tuple[str, str]]:
    """(image url, page title) in Google's result order. Needs a real browser: Google serves JS-only pages."""
    browser = next(p for p in EDGE if p.exists())
    url = "https://www.google.com/search?tbm=isch&hl=en&q=" + urllib.parse.quote(query)
    dom = subprocess.run(
        [str(browser), "--headless=new", "--disable-gpu", "--lang=en-US", "--window-size=1400,4000",
         "--virtual-time-budget=8000", "--dump-dom", url],
        capture_output=True, timeout=120,
    ).stdout.decode("utf-8", "ignore")
    urls = []
    for u, _h, _w in re.findall(r'\["(https?://[^"]+?)",(\d+),(\d+)\]', dom):
        u = u.encode().decode("unicode_escape")
        if "gstatic.com" not in u and u not in urls:
            urls.append(u)
    titles = [html.unescape(t) for t in re.findall(r'<img[^>]+alt="([^"]{8,})"', dom)]
    return [(u, titles[i] if i < len(titles) else "") for i, u in enumerate(urls)]


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.google.com/"})
        raw = urllib.request.urlopen(req, timeout=25).read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return False
    if min(img.size) < 80:
        return False
    img.thumbnail((1024, 1024))  # web/core.js compressForUpload
    img.save(dest, "JPEG", quality=85)
    return True


def predict(api: str, path: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="lang"\r\n\r\nen\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: image/jpeg\r\n\r\n".encode(),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        api.rstrip("/") + "/api/predict", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": UA},
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def summary(res: dict) -> dict:
    """What the farmer sees: the app's verdict in one row."""
    leaf = res.get("stage1_leaf_gate") or {}
    crop = res.get("stage2_leaf_type") or {}
    best = (res.get("stage3_disease") or {}).get("best_answer") or {}
    if leaf.get("is_leaf") is False:
        status = "not_leaf"
    elif crop.get("needs_user_pick"):
        status = "asks_crop"
    elif not best.get("prediction"):
        status = "no_disease"
    else:
        status = "diagnosed"
    return {
        "status": status,
        "leaf_conf": leaf.get("leaf_probability"),
        "crop": crop.get("crop"),
        "crop_conf": crop.get("confidence"),
        "crop_top3": [f"{t.get('crop')} {round(100 * (t.get('confidence') or 0))}%" for t in crop.get("top3") or []],
        "disease": best.get("prediction"),
        "disease_conf": best.get("confidence"),
        "message": res.get("message"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://agroscan.mujahidulhaquejihad.com")
    ap.add_argument("--per-query", type=int, default=20)
    ap.add_argument("--new-search", action="store_true", help="Search Google again instead of reusing search.json")
    args = ap.parse_args()
    (OUT / "images").mkdir(parents=True, exist_ok=True)

    # Frozen test set: re-runs (e.g. after a deploy) score the same images unless --new-search.
    search_file = OUT / "search.json"
    if args.new_search or not search_file.exists():
        picked, seen = [], set()
        for qi, query in enumerate(QUERIES):
            got = 0
            for url, title in google_images(query):
                if got >= args.per_query:
                    break
                if url in seen:
                    continue
                seen.add(url)
                name = f"q{qi}_{got:02d}"
                if download(url, OUT / "images" / f"{name}.jpg"):
                    picked.append({"id": name, "query": query, "title": title, "url": url})
                    got += 1
        search_file.write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    picked = json.loads(search_file.read_text(encoding="utf-8"))

    host = urllib.parse.urlparse(args.api).netloc.replace(":", "_")
    ans_dir = OUT / "answers" / host
    ans_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in picked:
        ans = ans_dir / f"{item['id']}.json"
        if not ans.exists():
            try:
                res = predict(args.api, OUT / "images" / f"{item['id']}.jpg")
            except Exception as exc:
                res = {"error": str(exc)}
            ans.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        res = json.loads(ans.read_text(encoding="utf-8"))
        row = {**item, **summary(res)}
        if "error" in res:
            row["status"] = "error"
        rows.append(row)
        print(f"{item['id']} {row['status']:<10} {row['crop']} | {row['disease']} | {item['title'][:50]}")
    (OUT / f"results_{host}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    report = OUT / f"report_{host}.html"
    report.write_text(report_html(rows, counts, args.api), encoding="utf-8")
    print(len(rows), "images", counts, "->", report)


SAYS = {
    "diagnosed": "Diagnosed",
    "asks_crop": "Asks the user to pick the crop",
    "not_leaf": "Says: not a leaf, send one clear leaf",
    "no_disease": "Could not diagnose",
    "error": "Server error / timeout",
}


def report_html(rows: list, counts: dict, api: str) -> str:
    esc = html.escape
    cards = []
    for r in rows:
        pct = lambda v: f"{round(100 * v)}%" if isinstance(v, (int, float)) else "—"
        detail = {
            "diagnosed": f"{esc(str(r['disease']))} ({pct(r['disease_conf'])})",
            "asks_crop": "Options: " + esc(", ".join(r["crop_top3"])) + ", Other",
            "not_leaf": f"leaf score {pct(r['leaf_conf'])}",
        }.get(r["status"], esc(str(r.get("message") or "")))
        cards.append(
            f'<div class="c {r["status"]}"><img src="images/{r["id"]}.jpg" loading="lazy">'
            f'<b>{SAYS.get(r["status"], r["status"])}</b><span>{detail}</span>'
            f'<small>{esc(r["id"])} · "{esc(r["query"])}" · <a href="{esc(r["url"])}">{esc(r["title"][:60])}</a></small></div>'
        )
    tally = " · ".join(f"{SAYS.get(k, k)}: <b>{v}</b>" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    return f"""<!doctype html><meta charset="utf-8"><title>AgroScan on Google Images</title>
<style>body{{font:14px system-ui;margin:24px;background:#f6f7f4}}.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}}
.c{{background:#fff;border-radius:8px;padding:8px;border-top:5px solid #999;display:flex;flex-direction:column;gap:4px}}
.c img{{width:100%;height:180px;object-fit:cover;border-radius:4px}}.diagnosed{{border-color:#2e7d32}}.asks_crop{{border-color:#f9a825}}
.not_leaf{{border-color:#c62828}}.error{{border-color:#000}}small{{color:#666}}</style>
<h1>AgroScan tested on {len(rows)} Google Images results</h1>
<p>Each image was sent to <code>{esc(api)}/api/predict</code> exactly as the web app sends it (resized to 1024 px, no crop chosen).</p>
<p>{tally}</p><div class="g">{''.join(cards)}</div>"""


if __name__ == "__main__":
    main()
