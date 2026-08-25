"""Make the repository importable when scripts are run directly.

Lets ``python scripts/wvs.py`` work in a fresh clone with no ``pip install``,
which is the shortest path to a working pipeline on Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
