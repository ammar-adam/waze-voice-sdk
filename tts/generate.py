"""Generate the phrases that are missing from the source media.

Equivalent to: python scripts/wvs.py synth

    python tts/generate.py --accept-voice-terms
    python tts/generate.py --model nano --accept-voice-terms
    python tts/generate.py --only and_then traffic_ahead --force
    python tts/generate.py --backend finetuned --model-path models/my-voice
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import replace  # noqa: E402

from waze_voice import config as config_module  # noqa: E402
from waze_voice import console  # noqa: E402
from waze_voice.steps import synth  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthesize navigation phrases in the voice of your cleaned clips.",
    )
    parser.add_argument("--phrases", type=Path, help="Phrase inventory JSON.")
    parser.add_argument("--output-dir", type=Path, help="Directory for synthesized clips.")
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument(
        "--backend",
        choices=synth.BACKENDS,
        help=(
            "chatterbox (default) clones zero-shot from your reference clips; "
            "xtts uses Coqui XTTS-v2, whose weights are non-commercial; "
            "finetuned loads your own checkpoint."
        ),
    )
    parser.add_argument(
        "--model",
        choices=synth.CHATTERBOX_MODELS,
        help="Chatterbox variant. nano is fastest on CPU; turbo is the default.",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        help="Speaker reference WAV. Built from audio/processed when omitted.",
    )
    parser.add_argument("--model-path", type=Path, help="Checkpoint dir for the finetuned backend.")
    parser.add_argument("--model-config", type=Path, help="config.json for the finetuned backend.")
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also fill optional phrases, not just required ones.",
    )
    parser.add_argument(
        "--accept-voice-terms",
        action="store_true",
        help="Acknowledge that you have the rights and consent to clone this voice.",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate clips that exist.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List which phrases would be synthesized, without loading a model.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)

    cfg = config_module.load(args.config)
    if args.model is not None:
        cfg = replace(cfg, synth=replace(cfg.synth, model=args.model))

    result = synth.run(
        config=cfg,
        phrases_path=args.phrases,
        output_dir=args.output_dir,
        backend=args.backend,
        reference=args.reference,
        model_path=args.model_path,
        model_config_path=args.model_config,
        only=args.only,
        include_optional=args.include_optional,
        accept_voice_terms=args.accept_voice_terms,
        force=args.force,
        dry_run=args.dry_run,
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
