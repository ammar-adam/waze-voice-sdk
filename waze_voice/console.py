"""ASCII-only console helpers.

Windows consoles still default to a legacy code page in plenty of setups, so the
SDK never prints non-ASCII characters. Every user-facing line goes through here.
"""

from __future__ import annotations

import sys
from typing import Iterable


_QUIET = False


def set_quiet(quiet: bool) -> None:
    global _QUIET
    _QUIET = quiet


def step(title: str) -> None:
    """Announce a pipeline stage."""
    if _QUIET:
        return
    print(f"\n== {title} " + "=" * max(0, 60 - len(title)))


def info(message: str) -> None:
    if _QUIET:
        return
    print(message)


def detail(message: str) -> None:
    if _QUIET:
        return
    print(f"  {message}")


def ok(message: str) -> None:
    if _QUIET:
        return
    print(f"  [ok] {message}")


def warn(message: str) -> None:
    print(f"  [warn] {message}", file=sys.stderr)


def error(message: str) -> None:
    print(f"  [error] {message}", file=sys.stderr)


def bullets(title: str, items: Iterable[str]) -> None:
    items = list(items)
    if not items:
        return
    print(f"\n{title}")
    for item in items:
        print(f"  - {item}")


def table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> None:
    """Print a fixed-width ASCII table."""
    if _QUIET:
        return
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def render(cells: tuple[str, ...]) -> str:
        return "  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(cells)).rstrip()

    print(render(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(render(row))
