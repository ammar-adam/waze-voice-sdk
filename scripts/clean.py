"""Optional cleanup hook for extracted clips."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def audio_files(directory: Path) -> list[Path]:
    files: list[Path] = []
    for extension in AUDIO_EXTENSIONS:
        files.extend(sorted(directory.glob(f"*{extension}")))
    return files


def copy_through(input_dir: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for source in audio_files(input_dir):
        shutil.copy2(source, output_dir / source.name)
        count += 1
    return count


def run_demucs(input_dir: Path, output_dir: Path) -> int:
    if shutil.which("demucs") is None:
        raise SystemExit("demucs was not found on PATH. Install Demucs or run with --mode copy.")

    files = audio_files(input_dir)
    if not files:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    for source in files:
        command = [
            "demucs",
            "--two-stems",
            "vocals",
            "--out",
            str(output_dir),
            str(source),
        ]
        subprocess.run(command, check=True)
    return len(files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean extracted clips or copy them through unchanged.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repo_root() / "audio" / "extracted",
        help="Directory containing extracted clips.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root() / "audio" / "processed",
        help="Directory for processed clips.",
    )
    parser.add_argument(
        "--mode",
        choices=("copy", "demucs"),
        default="copy",
        help="Cleanup mode. Use copy until Demucs workflow is configured.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.mode == "copy":
        count = copy_through(args.input_dir, args.output_dir)
    else:
        count = run_demucs(args.input_dir, args.output_dir)

    print(f"Processed {count} clip(s) into {args.output_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Cleanup command failed with exit code {error.returncode}") from None
