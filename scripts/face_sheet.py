"""Render face SVGs the way the site shows them: circle chips on a colour.

    python scripts/face_sheet.py out.png yoda shrek mario
    python scripts/face_sheet.py out.png --size 420 --dir drafts yoda

Colours come from site/characters.css, then roster/colors/*.json, then grey.
Needs resvg_py and Pillow (dev-only; nothing in the build uses this).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def colours() -> dict[str, str]:
    css = (REPO / "site" / "characters.css").read_text(encoding="utf-8")
    found = dict(re.findall(r"#([a-z0-9-]+)\s*\{\s*--bg:\s*(#[0-9a-fA-F]+)", css))
    for path in sorted((REPO / "roster" / "colors").glob("*.json")):
        for slug, value in json.loads(path.read_text(encoding="utf-8")).items():
            found.setdefault(slug, value["bg"])
    return found


def main(argv: list[str] | None = None) -> int:
    import resvg_py
    from PIL import Image, ImageDraw

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--dir", type=Path, default=REPO / "site" / "faces")
    parser.add_argument("--size", type=int, default=220)
    parser.add_argument("--cols", type=int, default=6)
    args = parser.parse_args(argv)

    n, bg = args.size, colours()
    cols = min(args.cols, len(args.slugs))
    rows = (len(args.slugs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (n + 10) + 10, rows * (n + 34) + 10), "white")
    draw = ImageDraw.Draw(sheet)
    for i, slug in enumerate(args.slugs):
        x, y = 10 + (i % cols) * (n + 10), 10 + (i // cols) * (n + 34)
        svg = (args.dir / f"{slug}.svg").read_text(encoding="utf-8")
        png = resvg_py.svg_to_bytes(svg_string=svg, width=int(n * 0.92), height=int(n * 0.92))
        chip = Image.new("RGBA", (n, n), bg.get(slug, "#e6e9f2"))
        face = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
        chip.alpha_composite(face, (int(n * 0.04),) * 2)
        mask = Image.new("L", (n, n), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, n - 1, n - 1), fill=255)
        sheet.paste(chip, (x, y), mask)
        draw.text((x, y + n + 6), slug, fill="black")
    sheet.save(args.out)
    print(f"{len(args.slugs)} faces -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
