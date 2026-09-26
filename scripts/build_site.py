"""Generate the site's derived files from site/voices.json.

voices.json is the single source for every UUID, so anything that embeds one
is generated from it: today that is the desktop QR codes. They are committed so
any static host (Vercel, Pages) can serve site/ as-is, and tests/test_site.py
fails if they no longer match voices.json. Rerun this after changing a UUID.

The QR codes encode the Waze link itself, not a backseatnav.com redirect. iOS only
hands a link to an app when the navigation starts from a user action; a camera
tap counts, a JavaScript redirect often does not, and the failure is silent - a
web page loads where the app should have opened.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import segno

SITE = Path(__file__).resolve().parent.parent / "site"


def qr_svg(uuid: str) -> bytes:
    """The QR code for one voice, byte-for-byte what the site serves."""
    buffer = io.BytesIO()
    segno.make(f"https://waze.com/ul?acvp={uuid}", error="m").save(
        buffer, kind="svg", scale=4, border=2, dark="#0e1520", light="#ffffff"
    )
    return buffer.getvalue()


def main() -> int:
    voices = json.loads((SITE / "voices.json").read_text(encoding="utf-8"))["voices"]
    out = SITE / "qr"
    out.mkdir(exist_ok=True)
    for stale in out.glob("*.svg"):
        stale.unlink()
    for voice in voices:
        (out / f"{voice['slug']}.svg").write_bytes(qr_svg(voice["uuid"]))
        print(f"  qr/{voice['slug']}.svg")
    print(f"{len(voices)} QR codes from voices.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
