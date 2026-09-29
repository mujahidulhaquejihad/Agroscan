"""auto_crop_leaf on a large canvas must finish quickly (no GrabCut)."""
from __future__ import annotations

import time

import numpy as np
from PIL import Image

from agroscan.leaf_crop import auto_crop_leaf


def main() -> None:
    arr = np.zeros((3000, 4000, 3), dtype=np.uint8)
    arr[:] = (240, 240, 240)
    arr[800:2200, 1200:2800] = (40, 160, 50)
    img = Image.fromarray(arr, "RGB")
    t0 = time.perf_counter()
    cropped, meta = auto_crop_leaf(img, isolate=True)
    elapsed = time.perf_counter() - t0
    assert meta.get("found"), meta
    assert cropped.size[0] < img.size[0] and cropped.size[1] < img.size[1]
    assert elapsed < 2.0, f"auto_crop_leaf took {elapsed:.2f}s"
    print("ok", round(elapsed, 3), "s", cropped.size, meta.get("method"))


if __name__ == "__main__":
    main()
