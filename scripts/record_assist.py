"""Walk the Waze in-app recorder prompt list one prompt at a time.

This is the fallback path, not the main one. Packs can be built from MP3 files
and uploaded, which preserves your audio quality; the in-app recorder captures
through the phone microphone and compresses hard. See HOW-TO-UPLOAD.md in the
export folder.

It is still here because it needs no third-party tooling, and because holding a
phone in one hand while finding and playing the right clip with the other is
miserable. This does the finding and playing.

Progress is saved after every prompt, so an interrupted session resumes where it
stopped.

    python scripts/record_assist.py
    python scripts/record_assist.py --resume
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import console, media, paths
from waze_voice.steps import export as export_step

PROGRESS_NAME = "record-progress.json"

_KEYS = "  [Enter] play    d done    r replay    s skip    q quit and save"


def _load_pack(export_dir: Path) -> list[dict]:
    manifest_path = export_dir / export_step.MANIFEST_NAME
    if not manifest_path.is_file():
        raise SystemExit(
            f"No pack manifest at {manifest_path}.\n"
            "Run the export step first: python scripts/wvs.py export"
        )
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {manifest_path}: {error}") from None

    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise SystemExit(f"{manifest_path} lists no clips.")
    return clips


def _load_progress(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    recorded = data.get("recorded")
    return recorded if isinstance(recorded, dict) else {}


def _save_progress(path: Path, recorded: dict[str, str]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "recorded": recorded,
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play exported clips one at a time while recording them in Waze.",
    )
    parser.add_argument("--export-dir", type=Path, help="Directory holding the export.")
    parser.add_argument("--resume", action="store_true", help="Skip prompts already marked done.")
    parser.add_argument("--restart", action="store_true", help="Clear saved progress first.")
    parser.add_argument(
        "--pack",
        help="Voice pack to work on. See: python scripts/wvs.py pack list",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pack:
        paths.set_active_pack(args.pack)
    export_dir = args.export_dir or paths.export_dir()

    clips = _load_pack(export_dir)
    progress_path = export_dir / PROGRESS_NAME

    if args.restart and progress_path.is_file():
        progress_path.unlink()

    recorded = {} if args.restart else _load_progress(progress_path)

    if not sys.stdin.isatty():
        raise SystemExit(
            "record_assist needs an interactive terminal. Run it directly rather "
            "than through a pipe."
        )

    console.step("Waze recorder assist")
    console.info(f"{len(clips)} prompt(s) in this pack.")
    console.info("")
    console.info("Before you start:")
    console.info("  1. Read " + export_step.GUIDE_NAME + " in the export folder.")
    console.info("  2. Open Waze: Settings > Voice and sound > Waze voice > Add a voice.")
    console.info("  3. Quiet room, phone 15-30 cm from your speaker, fixed volume.")
    console.info("")
    console.warn(
        "Waze asks for prompts in its own order. Match by wording, not by the "
        "number shown here."
    )
    console.detail(
        "Uploading the pack instead preserves audio quality. See "
        + export_step.GUIDE_NAME
    )

    index = 0
    while index < len(clips):
        clip = clips[index]
        phrase_id = str(clip.get("phrase_id", ""))

        if args.resume and recorded.get(phrase_id) == "done":
            index += 1
            continue

        path = export_dir / str(clip.get("file", ""))
        marker = " (done)" if recorded.get(phrase_id) == "done" else ""

        print(f"\n({index + 1}/{len(clips)}) {clip.get('label')}{marker}")
        print(f"  say:    \"{clip.get('text')}\"")
        print(
            f"  clip:   {path.name}  [{clip.get('duration_seconds')}s, "
            f"{clip.get('bitrate_kbps')} kbps]"
        )
        print(_KEYS)

        try:
            answer = input("  > ").strip().lower()
        except EOFError:
            answer = "q"

        if answer in ("", "p", "play", "r", "replay"):
            if not path.is_file():
                console.error(f"Clip file is missing: {path}")
                continue
            try:
                media.play(path)
            except media.MediaError as error:
                console.error(str(error))
            continue

        if answer in ("d", "done"):
            recorded[phrase_id] = "done"
            _save_progress(progress_path, recorded)
            index += 1
            continue

        if answer in ("s", "skip"):
            recorded[phrase_id] = "skipped"
            _save_progress(progress_path, recorded)
            index += 1
            continue

        if answer in ("q", "quit"):
            break

        console.warn(f"Unrecognized input {answer!r}.")

    _save_progress(progress_path, recorded)

    done = sum(1 for value in recorded.values() if value == "done")
    console.info("")
    console.info(
        f"Recorded {done} of {len(clips)} prompt(s). "
        f"Progress saved to {progress_path.name}."
    )
    console.info("Resume later with: python scripts/record_assist.py --resume")
    console.info("")
    console.info(
        "Now drive or simulate a route and confirm the prompts fire, then write "
        "what happened into docs/waze-import-spike.md."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.info("\nInterrupted.")
        sys.exit(130)
