"""Extract phrase clips from source media. Equivalent to: wvs.py extract"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import config as config_module
from waze_voice import console, paths
from waze_voice.steps import extract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract phrase clips from source media.")
    parser.add_argument("--sources", type=Path, help="CSV of phrase source timestamps.")
    parser.add_argument("--phrases", type=Path, help="Phrase inventory JSON.")
    parser.add_argument("--output-dir", type=Path, help="Directory for extracted WAV files.")
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID", help="Limit to these phrases.")
    parser.add_argument("--force", action="store_true", help="Re-cut clips that already exist.")
    parser.add_argument("--dry-run", action="store_true", help="Report cuts without running them.")
    parser.add_argument(
        "--pack",
        help="Voice pack to work on. See: python scripts/wvs.py pack list",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)
    if args.pack:
        paths.set_active_pack(args.pack)
        console.detail(f"Pack: {args.pack}")
    result = extract.run(
        config=config_module.load(args.config),
        sources_path=args.sources,
        phrases_path=args.phrases,
        output_dir=args.output_dir,
        only=args.only,
        force=args.force,
        dry_run=args.dry_run,
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
