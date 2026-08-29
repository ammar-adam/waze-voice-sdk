"""Build every character and stage it for upload, in one command.

Every character runs on a Fish Audio community model by default, so one key
covers the whole run.

Pooh and Tigger also have catalogue-voice presets, and `--catalogue` uses those
instead. That route matters more than its length here suggests: those two rest
on Milne's 1926 and 1928 books, whose copyright has expired, so they are the
only packs publishable without a rights argument. It is also the fallback when
a community model is withdrawn, which happens, or when Fish's free tier ends.

A missing key is not an error. Anything without a usable key is reported as
skipped, so this is safe to run before you have finished signing up.

    python scripts/build_all.py                  # all five, via Fish
    python scripts/build_all.py --catalogue      # pooh and tigger on OpenAI
    python scripts/build_all.py --only elmo      # just one
    python scripts/build_all.py --no-stage       # build, do not copy anywhere
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage_for_upload import DEFAULT_UPLOADER, build, stage  # noqa: E402

from waze_voice import console, packs, presets, providers  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# preset name -> the folder name, which is the voice name Waze shows the driver.
CHARACTERS: dict[str, str] = {
    "pooh": "Winnie the Pooh",
    "tigger": "Tigger",
    "paddington": "Paddington",
    "cookie-monster": "Cookie Monster",
    "elmo": "Elmo",
}

# Community models for the two presets whose own voice is a catalogue one.
# Kept here rather than in the preset files on purpose: pooh and tigger rest on
# an expired copyright and their presets should keep saying so. Routing them
# through a clone changes only how the lines are spoken, and the run says so.
FISH_VOICES: dict[str, str] = {
    "pooh": "cf6e370cb45240b492b14c70a18d0259",
    "tigger": "23ad79b4e84f46259dd256c0b01526c2",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="Repeatable.")
    parser.add_argument("--no-stage", action="store_true")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help=(
            "Keep clips that already exist instead of regenerating. For "
            "resuming an interrupted run; not for switching voice, since the "
            "old voice's clips would be kept without saying so."
        ),
    )
    parser.add_argument(
        "--catalogue",
        action="store_true",
        help=(
            "Build pooh and tigger from their licensed catalogue voice instead "
            "of a community model. Needs $OPENAI_API_KEY, and gives the two "
            "packs that carry no rights argument."
        ),
    )
    parser.add_argument("--uploader", type=Path, default=DEFAULT_UPLOADER)
    args = parser.parse_args(argv)

    wanted = args.only or list(CHARACTERS)
    unknown = [name for name in wanted if name not in CHARACTERS]
    if unknown:
        print(f"Unknown: {', '.join(unknown)}. Known: {', '.join(CHARACTERS)}")
        return 1

    built: list[str] = []
    skipped: list[tuple[str, str]] = []
    failed: list[str] = []

    for name in wanted:
        preset = presets.load(name)
        override_voice = "" if args.catalogue else FISH_VOICES.get(name, "")
        override_provider = "fish" if override_voice else ""
        provider = providers.get(override_provider or preset.provider)

        if not provider.key_present():
            skipped.append((name, f"needs ${provider.env_var}"))
            continue

        if not provider.key_looks_real():
            skipped.append((name, f"${provider.env_var} looks like a placeholder"))
            continue

        console.step(f"{preset.label}  ({provider.name}, {preset.rights.status})")
        if override_voice:
            console.detail(
                "Using a community model instead of this preset's catalogue "
                "voice. The lines are unchanged; the rights position of the "
                "voice is not the preset's."
            )

        # packs/ is git-ignored, so a fresh clone has none of these and the
        # build would fail on the first character with a message about a
        # missing pack rather than doing the obvious thing.
        if not packs.exists(name):
            packs.create(name, label=CHARACTERS[name])
            console.detail(f"Created pack {name}")

        if build(
            name,
            name,
            provider=override_provider,
            voice=override_voice,
            force=not args.reuse,
        ):
            failed.append(name)
            continue
        built.append(name)

        if not args.no_stage:
            if not args.uploader.is_dir():
                skipped.append((name, f"no uploader at {args.uploader}"))
                continue
            pack_dir = REPO / "packs" / name / "audio" / "export" / "pack"
            if stage(pack_dir, args.uploader, CHARACTERS[name]):
                failed.append(name)

    console.info("")
    console.table(
        [(n, "built") for n in built]
        + [(n, f"skipped: {why}") for n, why in skipped]
        + [(n, "FAILED") for n in failed],
        headers=("Character", "Result"),
    )

    if skipped:
        console.info("")
        console.detail("Skipped entries are missing a key, not broken.")
        console.detail("  OpenAI:      https://platform.openai.com/api-keys")
        console.detail("  Fish Audio:  https://fish.audio")

    if built and not args.no_stage:
        console.info("")
        console.detail("Then, from the uploader checkout:")
        console.detail('  $env:PYTHONIOENCODING = "utf-8"')
        console.detail(r"  .venv\Scripts\activate")
        console.detail(r"  python mp3_upload\main.py")
        console.detail("Save both URLs per pack. The UUID cannot be recovered later.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
