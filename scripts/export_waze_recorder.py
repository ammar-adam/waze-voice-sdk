"""Export ordered clips and a checklist for Waze recorder-assisted import."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_phrases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    phrases = data.get("phrases")
    if not isinstance(phrases, list):
        raise SystemExit("config/phrases.json must contain a 'phrases' list.")
    return [phrase for phrase in phrases if isinstance(phrase, dict)]


def clear_export_dir(export_dir: Path) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    for path in export_dir.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def checklist_lines(
    phrases: list[dict[str, Any]],
    copied: list[tuple[int, dict[str, Any], Path]],
    missing: list[dict[str, Any]],
) -> list[str]:
    lines = [
        "# Waze Recorder Import Checklist",
        "",
        "Use this checklist while recording prompts in the Waze app.",
        "",
        "1. Open Waze.",
        "2. Go to `Settings > Voice and sound > Waze voice > Add a voice`.",
        "3. For each prompt, play the matching exported clip near the phone microphone or use your verified import method.",
        "4. Mark each prompt complete after confirming it saved in Waze.",
        "",
        "## Exported Clips",
        "",
    ]

    copied_by_id = {str(phrase["id"]): (index, path) for index, phrase, path in copied}
    for phrase in phrases:
        phrase_id = str(phrase.get("id", ""))
        label = str(phrase.get("label", phrase_id))
        filename = str(phrase.get("filename", ""))
        required = "required" if phrase.get("required") else "optional"
        copied_record = copied_by_id.get(phrase_id)

        if copied_record:
            index, path = copied_record
            lines.append(f"- [ ] {index:03d} - {label} ({required}) - `{path.name}`")
        else:
            lines.append(f"- [ ] MISSING - {label} ({required}) - `{filename}`")

    if missing:
        lines.extend(["", "## Missing Clips", ""])
        for phrase in missing:
            lines.append(f"- {phrase.get('id')}: {phrase.get('label')} ({phrase.get('filename')})")

    lines.append("")
    return lines


def export_clips(master_dir: Path, export_dir: Path, phrases: list[dict[str, Any]]) -> tuple[list[tuple[int, dict[str, Any], Path]], list[dict[str, Any]]]:
    copied: list[tuple[int, dict[str, Any], Path]] = []
    missing: list[dict[str, Any]] = []

    for index, phrase in enumerate(phrases, start=1):
        filename = str(phrase.get("filename", "")).strip()
        source = master_dir / filename
        if not source.is_file():
            if phrase.get("required"):
                missing.append(phrase)
            continue

        phrase_id = str(phrase.get("id", f"phrase_{index}")).strip()
        destination = export_dir / f"{index:03d}_{phrase_id}_{filename}"
        shutil.copy2(source, destination)
        copied.append((index, phrase, destination))

    return copied, missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export ordered clips for Waze recorder workflow.")
    parser.add_argument(
        "--phrases",
        type=Path,
        default=repo_root() / "config" / "phrases.json",
        help="Phrase inventory JSON.",
    )
    parser.add_argument(
        "--master-dir",
        type=Path,
        default=repo_root() / "audio" / "master",
        help="Directory containing final audio files.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=repo_root() / "audio" / "export",
        help="Directory to write ordered export clips.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Create checklist even when required clips are missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phrases = load_phrases(args.phrases)
    clear_export_dir(args.export_dir)
    copied, missing = export_clips(args.master_dir, args.export_dir, phrases)

    checklist_path = args.export_dir / "IMPORT_CHECKLIST.md"
    checklist_path.write_text(
        "\n".join(checklist_lines(phrases, copied, missing)),
        encoding="utf-8",
    )

    print(f"Exported {len(copied)} clip(s) to {args.export_dir}")
    print(f"Wrote checklist: {checklist_path}")

    if missing:
        print("\nMissing required clips:")
        for phrase in missing:
            print(f"  - {phrase.get('id')}: {phrase.get('filename')}")
        if not args.allow_missing:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
