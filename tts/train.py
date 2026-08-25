"""Fine-tune a TTS model on your own clips.

Read this before running it: for a navigation voice pack, fine-tuning is usually
the wrong tool. A pack yields a couple of minutes of usable audio at best, and
fine-tuning below roughly ten minutes of clean transcribed speech tends to
overfit and sound worse than XTTS zero-shot cloning, which needs no training at
all. `python tts/generate.py` is the default path for good reason.

Fine-tuning earns its keep when you have a large, consistent corpus of one
speaker: an audiobook you narrated, a long interview you own, a podcast back
catalogue you have rights to.

What this does:

1. Checks preconditions (interpreter version, Coqui TTS, dataset, GPU).
2. Writes a VITS fine-tune config pointed at your dataset.
3. Hands off to Coqui's own trainer, which owns the training loop.

    python tts/prepare_dataset.py
    python tts/train.py --dataset datasets/voice --accept-voice-terms
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from waze_voice import console, media, paths  # noqa: E402
from waze_voice.steps import synth  # noqa: E402

FINETUNE_MINIMUM_SECONDS = 600.0

BASE_MODEL = "tts_models/en/vctk/vits"


def _check_preconditions(dataset: Path, *, force: bool) -> float:
    available, reason = synth.is_available()
    if not available:
        raise SystemExit(f"{reason}.\nSee docs/tts.md for the Windows setup.")

    metadata = dataset / "metadata.csv"
    wavs = dataset / "wavs"
    if not metadata.is_file() or not wavs.is_dir():
        raise SystemExit(
            f"{dataset} does not look like a prepared dataset.\n"
            "Run: python tts/prepare_dataset.py"
        )

    total = 0.0
    count = 0
    for path in sorted(wavs.glob("*.wav")):
        try:
            total += media.duration_seconds(path)
            count += 1
        except media.MediaError:
            continue

    console.info(f"Dataset: {count} clip(s), {total:.1f}s ({total / 60:.1f} min)")

    if total < FINETUNE_MINIMUM_SECONDS and not force:
        raise SystemExit(
            f"Only {total / 60:.1f} minutes of audio. Fine-tuning generally needs "
            f"at least {FINETUNE_MINIMUM_SECONDS / 60:.0f} minutes to beat zero-shot "
            "cloning, and below that it usually overfits.\n\n"
            "Use the default path instead:\n"
            "    python tts/generate.py --accept-voice-terms\n\n"
            "Or pass --force if you know what you are doing and want to try anyway."
        )

    try:
        import torch  # type: ignore[import-not-found]

        if not torch.cuda.is_available():
            console.warn(
                "No CUDA device found. Fine-tuning on CPU is impractically slow: "
                "expect days rather than hours."
            )
    except ImportError:
        console.warn("PyTorch not importable; the trainer will fail to start.")

    return total


def _write_config(dataset: Path, output_dir: Path, args: argparse.Namespace) -> Path:
    """Write the Coqui trainer config for a VITS fine-tune."""
    output_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "model": "vits",
        "run_name": args.run_name,
        "output_path": str(output_dir),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "eval_batch_size": max(1, args.batch_size // 2),
        "lr": args.learning_rate,
        "mixed_precision": True,
        "save_step": args.save_step,
        "print_step": 25,
        "run_eval": True,
        "test_delay_epochs": -1,
        "text_cleaner": "english_cleaners",
        "use_phonemes": True,
        "phoneme_language": "en-us",
        "phoneme_cache_path": str(output_dir / "phoneme_cache"),
        "datasets": [
            {
                "formatter": "ljspeech",
                "dataset_name": dataset.name,
                "path": str(dataset),
                "meta_file_train": "metadata.csv",
                "language": "en",
            }
        ],
        "audio": {"sample_rate": 22050},
    }

    config_path = output_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    console.detail(f"Wrote trainer config: {config_path}")
    return config_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune a TTS model on your own clips.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=paths.repo_root() / "datasets" / "voice",
        help="Prepared dataset directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=paths.repo_root() / "models" / "finetune",
        help="Where checkpoints are written. Git-ignored.",
    )
    parser.add_argument("--run-name", default="waze-voice-finetune")
    parser.add_argument("--restore-path", type=Path, help="Base checkpoint to fine-tune from.")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--save-step", type=int, default=1000)
    parser.add_argument(
        "--accept-voice-terms",
        action="store_true",
        help="Acknowledge that you have the rights and consent to train on this voice.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Train even when the dataset is smaller than the recommended minimum.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Write the config and print the trainer command without running it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    console.step("Fine-tune")
    synth.check_consent(accepted=args.accept_voice_terms)
    _check_preconditions(args.dataset, force=args.force)

    config_path = _write_config(args.dataset, args.output_dir, args)

    command = [sys.executable, "-m", "TTS.bin.train_tts", "--config_path", str(config_path)]
    if args.restore_path:
        command += ["--restore_path", str(args.restore_path)]
    else:
        console.detail(
            f"No --restore-path given. Training starts from scratch, which needs far "
            f"more data than fine-tuning from a base model such as {BASE_MODEL}."
        )

    printable = " ".join(command)
    if args.print_only:
        console.info("")
        console.info("Trainer command:")
        console.info(f"    {printable}")
        return 0

    console.info("")
    console.info(f"Handing off to the Coqui trainer:\n    {printable}")
    console.info("Checkpoints and logs go to " + str(args.output_dir))
    console.info("")

    try:
        result = subprocess.run(command, check=False)
    except FileNotFoundError:
        raise SystemExit(
            "Could not start the Coqui trainer. Confirm Coqui TTS is installed in "
            "this interpreter: python -m pip install -r requirements-tts.txt"
        ) from None

    if result.returncode != 0:
        console.error(f"Trainer exited with code {result.returncode}.")
        return result.returncode

    console.info("")
    console.info("Training finished. Generate with the fine-tuned checkpoint:")
    console.info(
        f"    python tts/generate.py --backend finetuned --model-path {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.info("\nInterrupted.")
        sys.exit(130)
