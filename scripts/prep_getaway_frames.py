"""First frames for THE GETAWAY's NEW shots (film/runway4/frames.json).

Each approved still is cropped to 1920x1080 and its generated text (licence
plates, emblems, sign glyphs) is painted out: the rectangle is filled by
diffusing its surroundings inwards (a harmonic inpaint), scaled by
`brightness`, given back a little grain and feathered into the frame by the
blur radius, so image-to-video starts from a frame with nothing readable in it. Writes
film/runway4/stills/<N>_first.png.

    python scripts/prep_getaway_frames.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

R4 = Path(__file__).resolve().parent.parent / "film" / "runway4"


def main() -> int:
    spec = json.loads((R4 / "frames.json").read_text(encoding="utf-8"))
    for name, s in spec.items():
        if name.startswith("_"):
            continue
        img = Image.open(R4 / s["src"]).convert("RGB")
        if img.width != 1920:
            img = img.resize((1920, round(img.height * 1920 / img.width)), Image.LANCZOS)
        y0 = s.get("crop_y", (img.height - 1080) // 2)
        img = img.crop((0, y0, 1920, y0 + 1080))
        out = np.asarray(img, np.float32)
        rng = np.random.default_rng(1)
        for x, y, w, h, px, bright in s["fix"]:
            pad = px * 3 + 4
            x0, y0b, x1, y1 = (
                max(0, x - pad),
                max(0, y - pad),
                min(1920, x + w + pad),
                min(1080, y + h + pad),
            )  # noqa: E501
            crop = out[y0b:y1, x0:x1].copy()
            inside = np.zeros(crop.shape[:2], bool)
            inside[y - y0b : y - y0b + h, x - x0 : x - x0 + w] = True
            fill = crop.copy()
            fill[inside] = crop[~inside].mean(0)
            for sigma in (8, 4, 2):
                for _ in range(60):
                    blurred = gaussian_filter(fill, (sigma, sigma, 0))
                    fill[inside] = blurred[inside]
            fill = fill * bright + rng.normal(0, 3.0, fill.shape)
            yy, xx = np.mgrid[y0b:y1, x0:x1]
            dx = np.clip(np.maximum(x - xx, xx - (x + w - 1)), 0, None) / max(1, px)
            dy = np.clip(np.maximum(y - yy, yy - (y + h - 1)), 0, None) / max(1, px)
            m = np.clip(1 - np.hypot(dx, dy), 0, 1)[..., None]
            out[y0b:y1, x0:x1] = crop * (1 - m) + fill * m
        dest = R4 / "stills" / f"{name}_first.png"
        Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dest)
        print(f"{name}: {s['src']} -> {dest.relative_to(R4)} ({len(s['fix'])} fixes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
