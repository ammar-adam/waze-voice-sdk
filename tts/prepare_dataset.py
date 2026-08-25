"""Build an LJSpeech-style dataset from cleaned clips, and report on its size.

Only needed for the fine-tuning path; the default backend clones zero-shot and
needs no dataset. Fine-tuning is only worth doing when there is enough
transcribed audio for it. This reports what you actually have before you spend
GPU hours finding out, and writes the dataset in the layout Coqui's recipes
expect:

    datasets/voice/
      metadata.csv        name|text|normalized_text, pipe delimited
      wavs/<name>.wav

    python tts/prepare_dataset.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from waze_voice import console, media, paths  # noqa: E402
from waze_voice.steps import synth  # noqa: E402

# Rough, widely-reported guidance for what different corpus sizes support.
ZERO_SHOT_MINIMUM = 6.0
ZERO_SHOT_COMFORTABLE = 30.0
FINETUNE_MINIMUM = 600.0  # ten minutes


def _corpus_seconds(dataset_dir: Path) -> tuple[float, int]:
    total = 0.0
    count = 0
    for path in sorted((dataset_dir / "wavs").glob("*.wav")):
        try:
            total += media.duration_seconds(path)
            count += 1
        except media.MediaError as error:
            console.warn(f"Could not probe {path.name}: {error}")
    return total, count


def _advise(total: float, count: int) -> None:
    console.info("")
    console.info(f"Corpus: {count} clip(s), {total:.1f}s total ({total / 60:.1f} min)")

    if total < ZERO_SHOT_MINIMUM:
        console.warn(
            f"Under {ZERO_SHOT_MINIMUM:.0f}s. Even zero-shot cloning will sound "
            "unlike the source. Extract more clips before going further."
        )
    elif total < FINETUNE_MINIMUM:
        console.info("")
        console.info(
            "This is a zero-shot sized corpus. Use the default Chatterbox backend, "
            "which conditions on the reference audio without any training:"
        )
        console.info("    python tts/generate.py --accept-voice-terms")
        console.info("")
        console.info(
            f"Fine-tuning generally needs upward of {FINETUNE_MINIMUM / 60:.0f} minutes "
            "of clean, accurately transcribed speech to beat zero-shot. Below that it "
            "usually overfits and sounds worse."
        )
    else:
        console.info("")
        console.info("Enough audio that fine-tuning may beat zero-shot. Next:")
        console.info("    python tts/train.py --dataset datasets/voice")
        console.info("")
        console.info("Compare against zero-shot before committing to the result.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Coqui-compatible dataset from audio/processed.",
    )
    parser.add_argument("--phrases", type=Path, help="Phrase inventory JSON.")
    parser.add_argument("--source-dir", type=Path, help="Directory of cleaned clips.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Dataset destination. Defaults to datasets/voice (Git-ignored).",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)

    console.step("Prepare dataset")
    dataset_dir = synth.prepare_dataset(
        phrases_path=args.phrases,
        source_dir=args.source_dir or paths.processed_dir(),
        destination=args.output_dir,
    )

    total, count = _corpus_seconds(dataset_dir)
    _advise(total, count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
