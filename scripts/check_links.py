"""Check that every voice on the site still resolves on Waze.

Reads site/voices.json, the single source for every UUID the site links to, and
asks Waze's CDN for each pack. Exits non-zero if any pack is gone, so CI can
act on it.

This check has already caught two generations of stale links. Waze has no
update-in-place, so every re-upload mints a new UUID, and a site that forgets to
follow is a site whose main button quietly stops working. During a launch that
is the worst possible failure, because nobody reports it: they just leave.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VOICES = Path(__file__).resolve().parent.parent / "site" / "voices.json"
CDN = "https://voice-prompts-ipv6.waze.com/{uuid}.tar.gz"
ATTEMPTS = 3
# A real pack is ~600 kB. Anything tiny is an error page, not a pack.
MIN_BYTES = 100_000


def check(uuid: str) -> tuple[bool, str]:
    last = ""
    for attempt in range(1, ATTEMPTS + 1):
        request = urllib.request.Request(
            CDN.format(uuid=uuid), method="HEAD", headers={"User-Agent": "backseat-link-check"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                size = int(response.headers.get("Content-Length") or 0)
                if size and size < MIN_BYTES:
                    return False, f"HTTP {response.status} but only {size} bytes"
                return True, f"HTTP {response.status}, {size / 1000:.0f} kB"
        except urllib.error.HTTPError as error:
            # 403/404 from the CDN means the pack is gone; retrying will not help.
            if error.code in (403, 404):
                return False, f"HTTP {error.code}"
            last = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError) as error:
            last = str(getattr(error, "reason", error))
        if attempt < ATTEMPTS:
            time.sleep(2 * attempt)
    return False, f"unreachable after {ATTEMPTS} attempts ({last})"


def main() -> int:
    voices = json.loads(VOICES.read_text(encoding="utf-8"))["voices"]
    failures = []
    for voice in voices:
        ok, detail = check(voice["uuid"])
        print(f"{'ok  ' if ok else 'FAIL'} {voice['slug']:16} {voice['uuid']}  {detail}")
        if not ok:
            failures.append(f"{voice['name']} ({voice['uuid']}): {detail}")

    print(f"\n{len(voices)} voices, {len(failures)} failing")
    if failures:
        print("\nBroken:")
        for line in failures:
            print(f"  - {line}")
        print("\nFix: re-upload the pack, put the new UUID in site/voices.json, push.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
