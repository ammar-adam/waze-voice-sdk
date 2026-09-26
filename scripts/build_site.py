"""Generate the site's derived files from site/voices.json.

Run locally and in the Pages workflow. voices.json is the single source for
every UUID, so anything that embeds one is generated from it rather than
committed: today that is the desktop QR codes.

The QR codes encode the Waze link itself, not a backseat.fm redirect. iOS only
hands a link to an app when the navigation starts from a user action; a camera
tap counts, a JavaScript redirect often does not, and the failure is silent - a
web page loads where the app should have opened.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import segno

SITE = Path(__file__).resolve().parent.parent / "site"


def main() -> int:
    voices = json.loads((SITE / "voices.json").read_text(encoding="utf-8"))["voices"]
    out = SITE / "qr"
    out.mkdir(exist_ok=True)
    for stale in out.glob("*.svg"):
        stale.unlink()
    for voice in voices:
        link = f"https://waze.com/ul?acvp={voice['uuid']}"
        segno.make(link, error="m").save(
            out / f"{voice['slug']}.svg", scale=4, border=2, dark="#0e1520", light="#ffffff"
        )
        print(f"  qr/{voice['slug']}.svg")
    print(f"{len(voices)} QR codes from voices.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
