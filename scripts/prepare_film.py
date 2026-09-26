"""Feed the Remotion project in film/ from the live packs.

Writes film/src/cuts.json (what each video says, in what order, for how long)
and copies the audio, faces and fonts into film/public/. The words come from
the presets and the audio from film-audio/, which build_film_audio.py cuts from
the exported packs, so a video can only say what a pack says. Run
build_film_audio.py first.

    python scripts/prepare_film.py
    cd film && npx remotion studio
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from waze_voice import presets  # noqa: E402

FILM = REPO / "film"
PUBLIC = FILM / "public"
AUDIO_IN = REPO / "film-audio"
FPS = 30
GAP = 0.3  # seconds between lines, as in the animatics

# Beat folder name -> the phrase it plays. Matches build_film_audio.BEATS.
BEATS = {"2-reroute": "reroute_chime", "3-police": "police_ahead", "4-arrive": "arrived"}
DEFAULT_LINES = {
    "2-reroute": "Recalculating.",
    "3-police": "Police reported ahead.",
    "4-arrive": "You have arrived.",
}

# The cuts in docs/launch-film.md. "default" is the stock-GPS cold open.
CUTS: dict[str, dict] = {
    "MissedTurn": {
        "hook": "POV: you missed your exit",
        "beat": "2-reroute",
        "scene": "exit",
        "order": [
            "default",
            "paddington",
            "hagrid",
            "cookie-monster",
            "gordon-ramsay",
            "eric-cartman",
            "batman",
            "darth-vader",
        ],
        "pause": "Next exit. Very carefully.",
        "button": ["eric-cartman", "4-arrive"],
    },
    "VaderOpen": {
        "hook": "your GPS, but it's Darth Vader",
        "beat": "2-reroute",
        "scene": "exit",
        "order": ["darth-vader", "eric-cartman", "elmo", "gordon-ramsay"],
        "pause": "",
        "button": ["eric-cartman", "4-arrive"],
    },
    "PoliceAhead": {
        "hook": "POV: police reported ahead",
        "beat": "3-police",
        "scene": "police",
        "order": [
            "default",
            "paddington",
            "hagrid",
            "daffy-duck",
            "gordon-ramsay",
            "eric-cartman",
            "batman",
            "darth-vader",
        ],
        "pause": "",
        "button": None,
    },
    "Arrived": {
        "hook": "POV: you made it",
        "beat": "4-arrive",
        "scene": "arrive",
        "order": ["default", "elmo", "hagrid", "bugs-bunny", "gordon-ramsay", "eric-cartman"],
        "pause": "",
        "button": None,
    },
}

FONTS = {
    "BagelFatOne.ttf": "https://github.com/google/fonts/raw/main/ofl/bagelfatone/BagelFatOne-Regular.ttf",
    "Bricolage.ttf": "https://github.com/google/fonts/raw/main/ofl/bricolagegrotesque/"
    "BricolageGrotesque%5Bopsz%2Cwdth%2Cwght%5D.ttf",
    "JetBrainsMono.ttf": "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/"
    "JetBrainsMono%5Bwght%5D.ttf",
}

DEFAULT_COLOURS = {"bg": "#dfe7f5", "tone": "#3b5bdb", "toneInk": "#ffffff"}


def colours() -> dict[str, dict[str, str]]:
    css = (REPO / "site" / "characters.css").read_text(encoding="utf-8")
    out = {}
    for slug, body in re.findall(r"#([a-z-]+)\s*\{([^}]*)\}", css):
        vals = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", body))
        out[slug] = {"bg": vals["bg"], "tone": vals["tone"], "toneInk": vals["tone-ink"]}
    return out


def seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def segment(slug: str, beat: str, palette: dict) -> dict:
    source = AUDIO_IN / slug / f"{beat}.mp3"
    if not source.is_file():
        raise SystemExit(f"missing {source.relative_to(REPO)}: run scripts/build_film_audio.py")
    dest = PUBLIC / "audio" / f"{slug}-{beat}.mp3"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    secs = seconds(source)
    if slug == "default":
        name, line = "Your GPS", DEFAULT_LINES[beat]
    else:
        preset = presets.load(slug)
        name, line = preset.label, preset.lines[BEATS[beat]]
    return {
        "slug": slug,
        "name": name,
        "line": line,
        "audio": f"audio/{slug}-{beat}.mp3",
        "frames": math.ceil((secs + GAP) * FPS),
        **palette.get(slug, DEFAULT_COLOURS),
    }


def main() -> int:
    palette = colours()
    cuts = {}
    for cut_id, spec in CUTS.items():
        cuts[cut_id] = {
            "hook": spec["hook"],
            "scene": spec["scene"],
            "pause": spec["pause"],
            "segments": [segment(s, spec["beat"], palette) for s in spec["order"]],
            "button": segment(*spec["button"], palette) if spec["button"] else None,
        }
    cast = [
        {"slug": v["slug"], **palette[v["slug"]]}
        for v in json.loads((REPO / "site" / "voices.json").read_text(encoding="utf-8"))["voices"]
    ]
    (FILM / "src" / "cuts.json").write_text(
        json.dumps({"fps": FPS, "cuts": cuts, "cast": cast}, indent=2) + "\n", encoding="utf-8"
    )

    faces = PUBLIC / "faces"
    faces.mkdir(parents=True, exist_ok=True)
    for svg in (REPO / "site" / "faces").glob("*.svg"):
        shutil.copyfile(svg, faces / svg.name)

    fonts = PUBLIC / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for name, url in FONTS.items():
        if not (fonts / name).is_file():
            with urllib.request.urlopen(url, timeout=60) as response:
                (fonts / name).write_bytes(response.read())

    for cut_id, cut in cuts.items():
        total = sum(s["frames"] for s in cut["segments"])
        total += cut["button"]["frames"] if cut["button"] else 0
        print(f"{cut_id:12} {len(cut['segments'])} lines, {total / FPS:.1f}s before the end card")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
