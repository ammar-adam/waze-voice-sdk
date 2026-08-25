"""Validate the phrase inventory and final audio coverage.

Kept as its own entry point because it is the first command a fresh clone runs.
Equivalent to `python scripts/wvs.py validate`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import config as config_module
from waze_voice import console
from waze_voice.steps import validate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate phrase metadata, clip coverage, and audio properties.",
    )
    parser.add_argument("--phrases", type=Path, help="Path to phrases.json.")
    parser.add_argument("--master-dir", type=Path, help="Directory containing final clips.")
    parser.add_argument("--sources", type=Path, help="Source inventory CSV to sanity check.")
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Report missing required clips without a failing exit code.",
    )
    parser.add_argument(
        "--no-audio-check",
        action="store_true",
        help="Skip ffprobe checks of channel count, sample rate, and duration.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)

    result = validate.run(
        config=config_module.load(args.config),
        phrases_path=args.phrases,
        master_dir=args.master_dir,
        sources_path=args.sources,
        check_audio=not args.no_audio_check,
    )

    if result.ok:
        return 0
    if args.allow_missing and not (result.property_problems or result.source_problems):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
