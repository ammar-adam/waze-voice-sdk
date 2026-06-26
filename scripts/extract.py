"""Extract phrase clips from local source media with ffmpeg."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_phrase_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    phrases = data.get("phrases", [])
    return {str(phrase["id"]) for phrase in phrases if isinstance(phrase, dict) and "id" in phrase}


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg was not found on PATH. Install ffmpeg before extracting clips.")


def read_sources(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    except FileNotFoundError:
        raise SystemExit(f"Missing source CSV: {path}") from None

    required_columns = {"phrase_id", "source_path", "start", "end", "take", "notes"}
    if not rows:
        return []

    missing = required_columns - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Source CSV missing columns: {', '.join(sorted(missing))}")

    return rows


def output_name(phrase_id: str, take: str) -> str:
    safe_take = take.strip() or "1"
    return f"{phrase_id}_take_{safe_take}.wav"


def extract_clip(row: dict[str, str], output_dir: Path) -> Path:
    phrase_id = row["phrase_id"].strip()
    source_path = Path(row["source_path"].strip()).expanduser()
    start = row["start"].strip()
    end = row["end"].strip()
    take = row["take"].strip()

    if not source_path.is_file():
        raise SystemExit(f"Source file does not exist for {phrase_id}: {source_path}")
    if not start or not end:
        raise SystemExit(f"Start and end are required for {phrase_id}.")

    output_path = output_dir / output_name(phrase_id, take)
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        start,
        "-to",
        end,
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        "44100",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract phrase clips from source media.")
    parser.add_argument(
        "--sources",
        type=Path,
        default=repo_root() / "data" / "sources.sample.csv",
        help="CSV containing phrase source timestamps.",
    )
    parser.add_argument(
        "--phrases",
        type=Path,
        default=repo_root() / "config" / "phrases.json",
        help="Phrase inventory JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root() / "audio" / "extracted",
        help="Directory for extracted WAV files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_ffmpeg()

    phrase_ids = load_phrase_ids(args.phrases)
    rows = read_sources(args.sources)

    if not rows:
        print("No source rows found.")
        return 0

    outputs: list[Path] = []
    for row in rows:
        phrase_id = row["phrase_id"].strip()
        if phrase_id not in phrase_ids:
            raise SystemExit(f"Unknown phrase_id in source CSV: {phrase_id}")
        outputs.append(extract_clip(row, args.output_dir))

    print(f"Extracted {len(outputs)} clip(s):")
    for output in outputs:
        print(f"  - {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"ffmpeg failed with exit code {error.returncode}") from None
