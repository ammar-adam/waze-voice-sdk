"""Canonical repository layout.

Every script resolves paths through this module so the directory contract lives
in exactly one place.
"""

from __future__ import annotations

import os
from pathlib import Path

# Point this at another directory to build a second voice pack from one clone,
# or to keep a test run out of the working tree. Everything under audio/ follows
# it, including the build manifest and the QA report.
AUDIO_ROOT_ENV = "WVS_AUDIO_ROOT"


def repo_root() -> Path:
    """Return the repository root, regardless of the caller's working directory."""
    return Path(__file__).resolve().parents[1]


def config_dir() -> Path:
    return repo_root() / "config"


def data_dir() -> Path:
    return repo_root() / "data"


def audio_root() -> Path:
    override = os.environ.get(AUDIO_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
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
    return config_dir() / "phrases.json"


def routes_path() -> Path:
    return config_dir() / "routes.sample.json"


def pipeline_config_path() -> Path:
    return config_dir() / "pipeline.json"


def sources_path() -> Path:
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
