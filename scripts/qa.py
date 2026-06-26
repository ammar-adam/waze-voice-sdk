"""Play route-like clip sequences for audio QA."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return data


def phrase_filename_map(phrases_path: Path) -> dict[str, str]:
    data = load_json(phrases_path)
    phrases = data.get("phrases")
    if not isinstance(phrases, list):
        raise SystemExit("config/phrases.json must contain a 'phrases' list.")

    result: dict[str, str] = {}
    for phrase in phrases:
        if isinstance(phrase, dict) and "id" in phrase and "filename" in phrase:
            result[str(phrase["id"])] = str(phrase["filename"])
    return result


def select_route(routes_path: Path, route_id: str | None) -> dict[str, Any]:
    data = load_json(routes_path)
    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise SystemExit("routes file must contain at least one route.")

    if route_id is None:
        route = routes[0]
    else:
        matches = [route for route in routes if isinstance(route, dict) and route.get("id") == route_id]
        if not matches:
            raise SystemExit(f"Route not found: {route_id}")
        route = matches[0]

    if not isinstance(route, dict):
        raise SystemExit("Selected route must be an object.")
    return route


def play_clip(path: Path) -> None:
    ffplay = shutil.which("ffplay")
    if ffplay:
        command = [
            ffplay,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            str(path),
        ]
        subprocess.run(command, check=True)
        return

    if path.suffix.lower() != ".wav":
        raise SystemExit("ffplay was not found on PATH. Install ffmpeg/ffplay to QA non-WAV clips.")

    escaped_path = str(path).replace("'", "''")
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(New-Object Media.SoundPlayer '{escaped_path}').PlaySync();",
    ]
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play final clips in a route-like QA sequence.")
    parser.add_argument(
        "--phrases",
        type=Path,
        default=repo_root() / "config" / "phrases.json",
        help="Phrase inventory JSON.",
    )
    parser.add_argument(
        "--routes",
        type=Path,
        default=repo_root() / "config" / "routes.sample.json",
        help="Route sequence JSON.",
    )
    parser.add_argument(
        "--route-id",
        help="Route ID to play. Defaults to the first route.",
    )
    parser.add_argument(
        "--master-dir",
        type=Path,
        default=repo_root() / "audio" / "master",
        help="Directory containing final clips.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print sequence without playing audio.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    filenames = phrase_filename_map(args.phrases)
    route = select_route(args.routes, args.route_id)
    phrase_ids = route.get("phrases")
    if not isinstance(phrase_ids, list):
        raise SystemExit("Selected route must contain a 'phrases' list.")

    pause_seconds = float(route.get("pause_seconds", 1.0))
    sequence: list[tuple[str, Path]] = []
    missing: list[str] = []

    for phrase_id_value in phrase_ids:
        phrase_id = str(phrase_id_value)
        filename = filenames.get(phrase_id)
        if filename is None:
            missing.append(f"{phrase_id} (unknown phrase)")
            continue
        path = args.master_dir / filename
        if not path.is_file():
            missing.append(f"{phrase_id} ({filename})")
            continue
        sequence.append((phrase_id, path))

    if missing:
        print("Missing clips for QA route:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print(f"QA route: {route.get('label', route.get('id', 'unnamed'))}")
    for phrase_id, path in sequence:
        print(f"  - {phrase_id}: {path.name}")
        if not args.dry_run:
            play_clip(path)
            time.sleep(pause_seconds)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Audio playback failed with exit code {error.returncode}") from None
