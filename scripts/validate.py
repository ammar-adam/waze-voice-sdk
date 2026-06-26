"""Validate phrase inventory and final audio coverage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_PHRASE_FIELDS = {"id", "label", "required", "filename", "status"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Missing config file: {path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from None

    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return data


def validate_phrase_shape(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    phrases = data.get("phrases")

    if not isinstance(phrases, list):
        return [], ["Top-level 'phrases' must be a list."]

    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()
    valid_phrases: list[dict[str, Any]] = []

    for index, phrase in enumerate(phrases, start=1):
        location = f"phrases[{index}]"
        if not isinstance(phrase, dict):
            errors.append(f"{location} must be an object.")
            continue

        missing_fields = sorted(REQUIRED_PHRASE_FIELDS - phrase.keys())
        if missing_fields:
            errors.append(f"{location} missing fields: {', '.join(missing_fields)}")
            continue

        phrase_id = phrase["id"]
        filename = phrase["filename"]
        required = phrase["required"]

        if not isinstance(phrase_id, str) or not phrase_id.strip():
            errors.append(f"{location}.id must be a non-empty string.")
        elif phrase_id in seen_ids:
            errors.append(f"Duplicate phrase id: {phrase_id}")
        else:
            seen_ids.add(phrase_id)

        if not isinstance(filename, str) or not filename.strip():
            errors.append(f"{location}.filename must be a non-empty string.")
        elif Path(filename).name != filename:
            errors.append(f"{location}.filename must be a filename, not a path: {filename}")
        elif filename in seen_filenames:
            errors.append(f"Duplicate filename: {filename}")
        else:
            seen_filenames.add(filename)

        if not isinstance(required, bool):
            errors.append(f"{location}.required must be true or false.")

        for field in ("label", "status"):
            if not isinstance(phrase[field], str) or not phrase[field].strip():
                errors.append(f"{location}.{field} must be a non-empty string.")

        valid_phrases.append(phrase)

    return valid_phrases, errors


def validate_master_coverage(
    phrases: list[dict[str, Any]],
    master_dir: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    present: list[dict[str, str]] = []
    missing_required: list[dict[str, str]] = []
    missing_optional: list[dict[str, str]] = []

    for phrase in phrases:
        filename = str(phrase["filename"])
        path = master_dir / filename
        record = {
            "id": str(phrase["id"]),
            "label": str(phrase["label"]),
            "filename": filename,
        }

        if path.is_file():
            present.append(record)
        elif phrase["required"]:
            missing_required.append(record)
        else:
            missing_optional.append(record)

    return present, missing_required, missing_optional


def print_records(title: str, records: list[dict[str, str]]) -> None:
    if not records:
        return

    print(f"\n{title}")
    for record in records:
        print(f"  - {record['id']}: {record['label']} ({record['filename']})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate phrase metadata and final audio coverage.",
    )
    parser.add_argument(
        "--phrases",
        type=Path,
        default=repo_root() / "config" / "phrases.json",
        help="Path to phrases.json.",
    )
    parser.add_argument(
        "--master-dir",
        type=Path,
        default=repo_root() / "audio" / "master",
        help="Directory containing final audio files.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Report missing required clips without returning a failing exit code.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = load_json(args.phrases)
    phrases, shape_errors = validate_phrase_shape(data)

    if shape_errors:
        print("Phrase inventory errors:")
        for error in shape_errors:
            print(f"  - {error}")
        return 2

    present, missing_required, missing_optional = validate_master_coverage(
        phrases=phrases,
        master_dir=args.master_dir,
    )

    required_count = sum(1 for phrase in phrases if phrase["required"])
    optional_count = len(phrases) - required_count

    print("Phrase inventory valid.")
    print(f"Total phrases: {len(phrases)}")
    print(f"Required phrases: {required_count}")
    print(f"Optional phrases: {optional_count}")
    print(f"Final clips present: {len(present)}")
    print(f"Missing required clips: {len(missing_required)}")
    print(f"Missing optional clips: {len(missing_optional)}")

    print_records("Missing required clips", missing_required)
    print_records("Missing optional clips", missing_optional)

    if missing_required and not args.allow_missing:
        print("\nValidation failed: required clips are missing.")
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
