"""Build every character and stage it for upload, in one command.

The five characters do not share a provider, and that is not an accident. Pooh
and Tigger rest on Milne's 1926 and 1928 books, whose copyright has expired, so
they are built from a licensed catalogue voice and are the two that can be
published without a rights argument. Paddington, Cookie Monster and Elmo are in
copyright, and are built from third-party community models that clone the
original performances.

A missing key is not an error here. Whichever half you have a key for gets
built, and the other half is reported as skipped, so this is safe to run
before you have finished signing up for anything.

    python scripts/build_all.py                 # everything you have keys for
    python scripts/build_all.py --only elmo     # just one
    python scripts/build_all.py --no-stage      # build, do not copy anywhere
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stage_for_upload import DEFAULT_UPLOADER, build, stage  # noqa: E402

from waze_voice import console, packs, presets, providers  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# Shorter than any real provider key, longer than every placeholder.
MIN_PLAUSIBLE_KEY = 20

# preset name -> the folder name, which is the voice name Waze shows the driver.
CHARACTERS: dict[str, str] = {
    "pooh": "Winnie the Pooh",
    "tigger": "Tigger",
    "paddington": "Paddington",
    "cookie-monster": "Cookie Monster",
    "elmo": "Elmo",
}

# Community models for the two presets that otherwise use a catalogue voice.
# Kept here rather than in the preset files on purpose: pooh and tigger rest on
# an expired copyright and their preset should keep saying so. --fish swaps only
# how the lines are spoken, and the run reports that it did.
FISH_VOICES: dict[str, str] = {
    "pooh": "cf6e370cb45240b492b14c70a18d0259",
    "tigger": "23ad79b4e84f46259dd256c0b01526c2",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="Repeatable.")
    parser.add_argument("--no-stage", action="store_true")
    parser.add_argument(
        "--fish",
        action="store_true",
        help=(
            "Build pooh and tigger from community models too, so every "
            "character is a cloned voice and one key covers the run."
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
        override_voice = FISH_VOICES.get(name, "") if args.fish else ""
        override_provider = "fish" if override_voice else ""
        provider = providers.get(override_provider or preset.provider)

        if not provider.key_present():
            skipped.append((name, f"needs ${provider.env_var}"))
            continue

        # A placeholder copied out of the README counts as "present" and then
        # fails as a 401, several requests in. Real keys are long; nothing this
        # short is one.
        key = os.environ.get(provider.env_var, "").strip()
        if len(key) < MIN_PLAUSIBLE_KEY or key.endswith("..."):
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

        if build(name, name, provider=override_provider, voice=override_voice):
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
