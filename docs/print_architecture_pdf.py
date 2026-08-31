"""Print the architecture HTML to a landscape A4 PDF via Edge or Chrome."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "agroscan-architecture.html"
PDF = ROOT / "AgroScan_Architecture.pdf"

BROWSERS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]


def main() -> int:
    if not HTML.exists():
        print(f"Missing {HTML}", file=sys.stderr)
        return 1
    browser = next((p for p in BROWSERS if p.exists()), None)
    if browser is None:
        print("Edge/Chrome not found", file=sys.stderr)
        return 2
    url = HTML.resolve().as_uri()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF}",
        "--print-to-pdf-no-header",
        url,
    ]
    print("Running:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        return r.returncode
    if not PDF.exists() or PDF.stat().st_size < 1000:
        print("PDF was not written", file=sys.stderr)
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        return 3
    print(f"Wrote {PDF} ({PDF.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
