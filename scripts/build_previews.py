"""Cut the site's three preview clips per character from packs that exist.

No API calls. A preview that costs a request per tap is a bill that scales with
virality, and these are the same files a driver hears, which is the honest
thing to preview anyway.

Beat 1 is two files joined the way Waze joins them, so it doubles as the
stitching test: if a character's distance clip ends badly against its maneuver
clip, this is where you hear it.

Imperial, matching the film and the North American launch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from waze_voice import media, phrases, presets  # noqa: E402

OUT = REPO / "site" / "audio"
VOICES = REPO / "site" / "voices.json"

CLIPS = [
    ("turn", ["in_quarter_mile", "turn_right"]),
    ("reroute", ["reroute_chime"]),
    ("arrive", ["arrived"]),
]

MIN_SECONDS = 0.8
MAX_SECONDS = 8.0
SILENT_LUFS = -60.0


def concat(parts: list[Path], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        destination.write_bytes(parts[0].read_bytes())
        return
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


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip() or 0)


def main() -> int:
    voices = json.loads(VOICES.read_text(encoding="utf-8"))["voices"]
    filenames = {p.id: p.waze_filename for p in phrases.load()}
    problems: list[str] = []
    said_by: dict[str, dict[str, str]] = {}

    print(f"{'character':16} {'clip':9} {'secs':>5} {'LUFS':>7}  says")
    for voice in voices:
        slug = voice["slug"]
        pack = REPO / "packs" / voice["preset"] / "audio" / "export" / "pack"
        preset = presets.load(voice["preset"])
        for label, ids in CLIPS:
            parts = [pack / filenames[i] for i in ids]
            if any(not p.is_file() for p in parts):
                problems.append(f"{slug}/{label}: source clip missing")
                continue
            dest = OUT / f"{slug}-{label}.mp3"
            concat(parts, dest)

            secs = duration(dest)
            try:
                lufs = media.measure_loudness(
                    dest, target_lufs=-16.0, true_peak_db=-1.5, loudness_range=11.0
                ).integrated_lufs
            except media.MediaError:
                lufs = -99.0
            said = " ".join(preset.lines[i] for i in ids)
            said_by.setdefault(slug, {})[label] = said
            print(f"{slug:16} {label:9} {secs:5.1f} {lufs:7.1f}  {said[:44]}")

            if lufs <= SILENT_LUFS:
                problems.append(f"{slug}/{label}: silent ({lufs:.0f} LUFS)")
            if not MIN_SECONDS <= secs <= MAX_SECONDS:
                problems.append(f"{slug}/{label}: {secs:.1f}s outside {MIN_SECONDS}-{MAX_SECONDS}s")

    # The words under each playing clip come from here, so the page shows what
    # the pack says rather than what someone remembers it saying.
    (OUT / "lines.json").write_text(
        json.dumps(said_by, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    total = sum(len(CLIPS) for _ in voices)
    print(f"\n{total} clips in {OUT.relative_to(REPO).as_posix()}/")
    if problems:
        print("\nPROBLEMS:")
        for line in problems:
            print(f"  {line}")
        return 1
    print("all clips present, audible, and sensibly sized")
    print("\nListen to every *-turn.mp3: that is the pairing Waze stitches at drive time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
