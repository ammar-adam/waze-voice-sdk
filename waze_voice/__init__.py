"""Waze Voice SDK core library.

Every pipeline step is implemented here and exposed through thin CLI wrappers in
``scripts/``. Keeping the logic in one importable package stops the six CLIs from
drifting apart on things like phrase loading, ffmpeg invocation, and take
selection.
"""

from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["__version__"]
