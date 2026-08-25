"""Pipeline stages.

Each module exposes a ``run(...)`` function returning a result dataclass, so the
orchestrator in ``scripts/wvs.py`` and the individual CLIs share one code path.
"""

from __future__ import annotations

__all__ = ["extract", "clean", "synth", "normalize", "qa", "export", "validate"]
