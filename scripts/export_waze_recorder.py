"""Export ordered clips plus import paperwork. Equivalent to: wvs.py export"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import config as config_module
from waze_voice import console
from waze_voice.steps import export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export ordered clips, a recording checklist, and an import "
            "verification guide."
        ),
    )
    parser.add_argument("--phrases", type=Path, help="Phrase inventory JSON.")
    parser.add_argument("--master-dir", type=Path, help="Directory containing final clips.")
    parser.add_argument("--export-dir", type=Path, help="Directory to write the export into.")
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Export an incomplete pack when required clips are missing.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)
    result = export.run(
        config=config_module.load(args.config),
        phrases_path=args.phrases,
        master_dir=args.master_dir,
        export_dir=args.export_dir,
        allow_missing=args.allow_missing,
    )
    return 0 if (result.ok or args.allow_missing) else 1


if __name__ == "__main__":
    sys.exit(main())
