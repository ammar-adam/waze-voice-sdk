"""Normalize final navigation clips with ffmpeg."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


INPUT_DIR_NAMES = ("processed", "synthesized", "extracted")
INPUT_EXTENSIONS = (".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg was not found on PATH. Install ffmpeg before normalizing clips.")


def load_phrases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    phrases = data.get("phrases")
    if not isinstance(phrases, list):
        raise SystemExit("config/phrases.json must contain a 'phrases' list.")
    return [phrase for phrase in phrases if isinstance(phrase, dict)]


def find_input_clip(audio_root: Path, phrase_id: str) -> Path | None:
    candidates: list[Path] = []
    for directory_name in INPUT_DIR_NAMES:
        directory = audio_root / directory_name
        for extension in INPUT_EXTENSIONS:
            candidates.extend(sorted(directory.glob(f"{phrase_id}*{extension}")))
    return candidates[0] if candidates else None


def normalize_clip(input_path: Path, output_path: Path, lufs: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-af",
        f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(output_path),
    ]
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize phrase clips into audio/master.")
    parser.add_argument(
        "--phrases",
        type=Path,
        default=repo_root() / "config" / "phrases.json",
        help="Phrase inventory JSON.",
    )
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=repo_root() / "audio",
        help="Root audio directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root() / "audio" / "master",
        help="Directory for normalized MP3 files.",
    )
    parser.add_argument(
        "--lufs",
        type=float,
        default=-16.0,
        help="Integrated loudness target.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_ffmpeg()
    phrases = load_phrases(args.phrases)

    normalized: list[Path] = []
    missing: list[str] = []

    for phrase in phrases:
        phrase_id = str(phrase.get("id", "")).strip()
        filename = str(phrase.get("filename", "")).strip()
        if not phrase_id or not filename:
            continue

        input_path = find_input_clip(args.audio_root, phrase_id)
        if input_path is None:
            if phrase.get("required"):
                missing.append(phrase_id)
            continue

        output_path = args.output_dir / filename
        normalize_clip(input_path, output_path, args.lufs)
        normalized.append(output_path)

    print(f"Normalized {len(normalized)} clip(s).")
    for path in normalized:
        print(f"  - {path}")

    if missing:
        print("\nMissing required source clips:")
        for phrase_id in missing:
            print(f"  - {phrase_id}")
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"ffmpeg failed with exit code {error.returncode}") from None
