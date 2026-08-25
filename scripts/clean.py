"""Isolate the vocal in extracted clips. Equivalent to: wvs.py clean"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import config as config_module
from waze_voice import console
from waze_voice.steps import clean


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean extracted clips with Demucs, ffmpeg filters, or pass them through.",
    )
    parser.add_argument("--input-dir", type=Path, help="Directory of extracted clips.")
    parser.add_argument("--output-dir", type=Path, help="Directory for processed clips.")
    parser.add_argument(
        "--mode",
        choices=clean.MODES,
        help="copy (no processing), ffmpeg (band-limit plus denoise), demucs (vocal separation).",
    )
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)
    result = clean.run(
        config=config_module.load(args.config),
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        only=args.only,
        force=args.force,
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
