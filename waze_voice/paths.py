"""Canonical repository layout.

Every script resolves paths through this module so the directory contract lives
in exactly one place.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Point this at another directory to keep a run out of the working tree.
# Everything under audio/ follows it, including the build manifest and the QA
# report. Takes precedence over the active pack.
AUDIO_ROOT_ENV = "WVS_AUDIO_ROOT"

# Selects a pack without passing --pack to every command.
PACK_ENV = "WVS_PACK"

PACKS_DIRNAME = "packs"

# Pack names become directory names, so they are restricted rather than escaped.
# Anything with a separator or a dot segment is rejected outright: `--pack ..`
# resolving to the repo root would put a delete-happy export step somewhere it
# has no business being.
PACK_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_active_pack: str | None = None


def repo_root() -> Path:
    """Return the repository root, regardless of the caller's working directory."""
    return Path(__file__).resolve().parents[1]


def validate_pack_name(name: str) -> str:
    """Return ``name`` if it is safe to use as a directory name, else exit."""
    candidate = (name or "").strip()
    if not PACK_NAME_PATTERN.match(candidate) or candidate in {".", ".."}:
        raise SystemExit(
            f"Invalid pack name {name!r}. Use letters, digits, dot, dash, or "
            "underscore, starting with a letter or digit. No path separators."
        )
    return candidate


def set_active_pack(name: str | None) -> None:
    """Point every subsequent path lookup at a pack, or back at the default tree."""
    global _active_pack
    _active_pack = validate_pack_name(name) if name else None


def active_pack() -> str | None:
    if _active_pack:
        return _active_pack
    from_env = os.environ.get(PACK_ENV)
    return validate_pack_name(from_env) if from_env else None


def packs_dir() -> Path:
    return repo_root() / PACKS_DIRNAME


def pack_root(name: str) -> Path:
    return packs_dir() / validate_pack_name(name)


def config_dir() -> Path:
    return repo_root() / "config"


def data_dir() -> Path:
    return repo_root() / "data"


def audio_root() -> Path:
    """Where this run's working audio lives.

    An explicit ``WVS_AUDIO_ROOT`` wins over the active pack, so a test or a
    one-off can redirect the tree without disturbing pack selection.
    """
    override = os.environ.get(AUDIO_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    pack = active_pack()
    if pack:
        return pack_root(pack) / "audio"
    return repo_root() / "audio"


def raw_dir() -> Path:
    return audio_root() / "raw"


def extracted_dir() -> Path:
    return audio_root() / "extracted"


def processed_dir() -> Path:
    return audio_root() / "processed"


def synthesized_dir() -> Path:
    return audio_root() / "synthesized"


def master_dir() -> Path:
    return audio_root() / "master"


def export_dir() -> Path:
    return audio_root() / "export"


def work_dir() -> Path:
    """Scratch space for intermediate renders. Ignored by Git."""
    return audio_root() / ".work"


def phrases_path() -> Path:
    """The active pack's inventory if it has one, otherwise the shared default.

    Most packs want the shared inventory: the Waze slot list is the same
    whatever voice fills it. A pack only needs its own copy when it changes the
    wording, the ``tts_text``, or the budget weights.
    """
    pack = active_pack()
    if pack:
        override = pack_root(pack) / "phrases.json"
        if override.is_file():
            return override
    return config_dir() / "phrases.json"


def routes_path() -> Path:
    pack = active_pack()
    if pack:
        override = pack_root(pack) / "routes.json"
        if override.is_file():
            return override
    return config_dir() / "routes.sample.json"


def pipeline_config_path() -> Path:
    return config_dir() / "pipeline.json"


def sources_path() -> Path:
    """The active pack's source inventory, otherwise the shared sample."""
    pack = active_pack()
    if pack:
        override = pack_root(pack) / "sources.csv"
        if override.is_file():
            return override
    return data_dir() / "sources.sample.csv"


def manifest_path() -> Path:
    return audio_root() / "build-manifest.json"


def qa_report_path() -> Path:
    return audio_root() / "qa-report.json"


def ensure_dirs() -> None:
    """Create every working directory the pipeline writes into."""
    for directory in (
        raw_dir(),
        extracted_dir(),
        processed_dir(),
        synthesized_dir(),
        master_dir(),
        export_dir(),
        work_dir(),
    ):
        directory.mkdir(parents=True, exist_ok=True)
