"""Cut the film's beats from every pack, and write the line sheet.

The film's Product Rule is that every spoken line corresponds to a real Waze
prompt. The only way to keep that true is to take the lines from the packs that
are actually live rather than from a script document, so this reads the presets
and the exported audio and reports what they really say.

Four beats, the same slots for every character:

    1. in_quarter_mile + turn_right   two files Waze plays back to back
    2. reroute_chime                  TickerPoints.mp3, the film's hero beat
    3. police_ahead                   Police.mp3
    4. arrived                        Arrive.mp3

The film is built on beat 2: you missed the turn, and twelve characters react.
See docs/launch-film.md for the cut.

Imperial, because the film is for a North American audience and the end card
has to match what a viewer hears on their own phone.

The Default track is not a pack. It is four lines generated flat for the film,
since the first loop has to sound like stock navigation before the joke lands.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from waze_voice import media, phrases, presets, providers  # noqa: E402

OUT = REPO / "film-audio"

# The beats, as (label, [phrase ids]). The first is two files because
# that is how Waze says it: distance, then maneuver.
BEATS = [
    ("1-quarter-mile-turn-right", ["in_quarter_mile", "turn_right"]),
    ("2-reroute", ["reroute_chime"]),
    ("3-police", ["police_ahead"]),
    ("4-arrive", ["arrived"]),
]

# The reroute supercut, in cut order: sweet to menacing, so every cut is a
# harder turn than the last and Vader closes it. docs/launch-film.md has why.
FILM = [
    "paddington",
    "elmo",
    "pooh",
    "cookie-monster",
    "bugs-bunny",
    "daffy-duck",
    "terminator",
    "batman",
    "eric-cartman",
    "vito-corleone",
    "darth-vader",
]
# In the end card and the follow-up posts, not the supercut.
END_CARD = ["tigger"]

# Flat, stock-sounding. Not Waze's own voice and not Google's - the film is
# unaffiliated, so the "before" state has to be ours too.
DEFAULT_VOICE = "f956b5efde2b4d68b87959395b8d8eb8"  # Informative Navigation Guide
DEFAULT_ALT = "63d5460e91e2411fa2e6bf95e7456f03"  # Anchor News, if the first is wrong
DEFAULT_LINES = {
    "1-quarter-mile-turn-right": "In a quarter mile, turn right.",
    "2-reroute": "Recalculating.",
    "3-police": "Police reported ahead.",
    "4-arrive": "You have arrived.",
}


def concat(parts: list[Path], destination: Path) -> Path:
    """Join clips the way Waze does: back to back, no gap."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        destination.write_bytes(parts[0].read_bytes())
        return destination
    listing = destination.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(destination),
        ],
        check=True,
    )
    listing.unlink()
    return destination


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip() or 0)


def cut_pack(name: str, filenames: dict[str, str]) -> list[dict]:
    """The three beats for one character, from its exported pack."""
    pack = REPO / "packs" / name / "audio" / "export" / "pack"
    preset = presets.load(name)
    rows = []
    for label, ids in BEATS:
        parts = [pack / filenames[i] for i in ids]
        missing = [p.name for p in parts if not p.is_file()]
        if missing:
            rows.append({"beat": label, "said": f"MISSING {missing}", "file": "", "secs": 0})
            continue
        dest = OUT / name / f"{label}.mp3"
        concat(parts, dest)
        rows.append(
            {
                "beat": label,
                "said": " ".join(preset.lines[i] for i in ids),
                "file": dest.relative_to(REPO).as_posix(),
                "secs": duration(dest),
            }
        )
    return rows


def make_default(model: str, folder: str) -> list[dict]:
    """Three lines, generated flat. Not a pack - the film only needs these."""
    provider = providers.FishAudio.from_env()
    rows = []
    for label, text in DEFAULT_LINES.items():
        dest = OUT / folder / f"{label}.mp3"
        dest.parent.mkdir(parents=True, exist_ok=True)
        provider.synthesize(text, model, dest)
        rows.append(
            {
                "beat": label,
                "said": text,
                "file": dest.relative_to(REPO).as_posix(),
                "secs": duration(dest),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-default",
        action="store_true",
        help="Do not spend API calls regenerating the Default track.",
    )
    args = parser.parse_args(argv)

    filenames = {p.id: p.waze_filename for p in phrases.load()}
    sheet: dict[str, list[dict]] = {}

    if not args.skip_default:
        print("Default (Informative Navigation Guide)")
        sheet["default"] = make_default(DEFAULT_VOICE, "default")
        print("Default alternate (Anchor News)")
        sheet["default-alt"] = make_default(DEFAULT_ALT, "default-alt")

    for name in FILM + END_CARD:
        print(f"{name}")
        sheet[name] = cut_pack(name, filenames)

    write_sheet(sheet)
    quiet = [
        f"{who}/{row['beat']}"
        for who, rows in sheet.items()
        for row in rows
        if row["file"] and _silent(REPO / row["file"])
    ]
    print(f"\n{sum(len(v) for v in sheet.values())} clips in {OUT.relative_to(REPO)}/")
    print("silent clips:", quiet or "none")
    return 0


def _silent(path: Path) -> bool:
    try:
        loud = media.measure_loudness(
            path, target_lufs=-16.0, true_peak_db=-1.5, loudness_range=11.0
        )
    except media.MediaError:
        return True
    return loud.integrated_lufs <= -60.0


def write_sheet(sheet: dict[str, list[dict]]) -> None:
    lines = [
        "# Film line sheet",
        "",
        "Generated by `scripts/build_film_audio.py` from the presets that are",
        "live on Waze. **Do not hand-edit.** If a line here does not work for the",
        "film, change the preset and rebuild the pack, so the film and the",
        "product never disagree.",
        "",
        "Four beats, the same slots for every character. The film is cut from",
        "beat 2; see [launch-film.md](launch-film.md).",
        "",
        "| Beat | Slots | Waze files |",
        "| --- | --- | --- |",
        "| 1 | `in_quarter_mile` + `turn_right` | `400.mp3` then `TurnRight.mp3` |",
        "| 2 | `reroute_chime` | `TickerPoints.mp3` |",
        "| 3 | `police_ahead` | `Police.mp3` |",
        "| 4 | `arrived` | `Arrive.mp3` |",
        "",
        "Beat 1 is two files because that is how Waze says it: the distance clip,",
        "then the maneuver clip, back to back. The cut audio here is joined the",
        "same way, so what you drop on the timeline is what a driver hears.",
        "",
        'Imperial throughout. `400.mp3` is "a quarter of a mile" - the imperial',
        "filenames do not match their numbers, which is documented in",
        "[waze-import-spike.md](waze-import-spike.md).",
        "",
        "---",
        "",
    ]

    order = [
        (
            "default",
            "Cold open: Default",
            "Generated for the film, not a pack. Flat, stock-GPS delivery. The cold open.",
        ),
        ("default-alt", "Cold open alternate", "Second option if the first reads too warm."),
    ] + [
        (key, f"{i}. {presets.load(key).label}", presets.load(key).description)
        for i, key in enumerate(FILM, 1)
    ]
    for key, title, note in order:
        rows = sheet.get(key)
        if not rows:
            continue
        lines += [
            f"## {title}",
            "",
            f"*{note}*",
            "",
            "| Beat | What it says | Clip | Length |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f'| {row["beat"]} | "{row["said"]}" | `{row["file"]}` | {row["secs"]:.1f}s |'
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Not in the supercut",
        "",
        "In the end card and the follow-up posts.",
        "",
    ]
    for key in END_CARD:
        rows = sheet.get(key)
        if not rows:
            continue
        label = presets.load(key).label
        lines += [
            f"### {label}",
            "",
            "| Beat | What it says | Clip | Length |",
            "| --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f'| {row["beat"]} | "{row["said"]}" | `{row["file"]}` | {row["secs"]:.1f}s |'
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Notes for the edit",
        "",
        "**Beat 2 is the odd one.** `reroute_chime` maps to `TickerPoints.mp3`,",
        "which is nominally a chime slot - three of eleven real packs ship it",
        "silent. Ours speak there. If a loop wants silence on the reroute, that",
        "is a legitimate reading of the slot, not a missing file.",
        "",
        '**Two lines from the first draft do not exist.** There is no "in 500',
        'feet" and no "continue for 0.3 miles" anywhere in Waze\'s vocabulary.',
        "The imperial distances are exactly four: a tenth of a mile, a quarter,",
        "a half, and one mile. Anything else in the film is a line the product",
        "cannot deliver.",
        "",
        "**The Default track is ours.** Not Waze's own voice and not Google's -",
        "a model cloning Google Maps' navigation voice exists on Fish and is",
        "deliberately not used here. The film is unaffiliated promo, so the",
        '"before" state has to be something we generated.',
        "",
    ]

    path = REPO / "docs" / "film-line-sheet.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    raise SystemExit(main())
