"""waze-voice-sdk command line.

    python scripts/wvs.py doctor
    python scripts/wvs.py run --sources data/my-sources.csv
    python scripts/wvs.py qa --route highway_merge

The implementation lives in waze_voice/cli.py so that an installed copy exposes
the same commands as a `wvs` executable. This shim exists so a fresh clone works
with no install step.
"""

from __future__ import annotations

import sys

import _bootstrap  # noqa: F401  (sys.path side effect)

from waze_voice import console
from waze_voice.cli import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.info("\nInterrupted.")
        sys.exit(130)
