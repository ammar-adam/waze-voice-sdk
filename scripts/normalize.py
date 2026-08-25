"""Loudness-normalize clips into audio/master. Equivalent to: wvs.py normalize"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import config as config_module
from waze_voice import console
from waze_voice.steps import normalize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize phrase clips into audio/master.")
    parser.add_argument("--phrases", type=Path, help="Phrase inventory JSON.")
    parser.add_argument("--sources", type=Path, help="Source CSV, read for take preferences.")
    parser.add_argument("--audio-root", type=Path, help="Root audio directory.")
    parser.add_argument("--output-dir", type=Path, help="Directory for normalized files.")
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument("--lufs", type=float, help="Override the integrated loudness target.")
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)

    cfg = config_module.load(args.config)
    if args.lufs is not None:
        cfg = config_module.PipelineConfig(
            audio=cfg.audio,
            loudness=config_module.LoudnessConfig(
                target_lufs=args.lufs,
                true_peak_db=cfg.loudness.true_peak_db,
                loudness_range=cfg.loudness.loudness_range,
                short_clip_seconds=cfg.loudness.short_clip_seconds,
                tolerance_lu=cfg.loudness.tolerance_lu,
            ),
            trim=cfg.trim,
            extract=cfg.extract,
            clean=cfg.clean,
            synth=cfg.synth,
            qa=cfg.qa,
        )

    result = normalize.run(
        config=cfg,
        phrases_path=args.phrases,
        sources_path=args.sources,
        audio_root=args.audio_root,
        output_dir=args.output_dir,
        only=args.only,
        force=args.force,
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
