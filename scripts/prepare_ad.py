"""Stage the 30s ad's media for Remotion and measure it.

film/runway/ holds the Runway footage, score and sound effects; film/voices/
holds the four voice lines cut from the live packs (build them with
scripts/build_ad_voices.py). This copies the clips into film/public/ad/,
loudness-normalises every audio source to -16 LUFS so the dB levels in
film/src/config.ts mean the same thing for every element, and writes
film/src/ad-media.json with each source's exact duration.

    python scripts/prepare_ad.py
    cd film && npx remotion studio
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

FILM = Path(__file__).resolve().parent.parent / "film"
RUNWAY = FILM / "runway"
VOICES = FILM / "voices"
OUT = FILM / "public" / "ad"

CLIPS = ["1A", "1B", "2A", "2B", "3A", "3B", "4A"]
STILLS = {"4B": "4B_still.webp"}
AUDIO = ["score", "sfx_rain", "sfx_dusk", "sfx_truck", "sfx_surge", "sfx_signal"]
VOICE_LINES = ["pooh", "batman", "elmo", "cookie"]


def seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def normalise(source: Path, dest: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-y", "-i", str(source),
            "-af", "loudnorm=I=-16:TP=-2:LRA=11", "-ar", "48000", "-ac", "2", str(dest),
        ],
        check=True,
    )  # fmt: skip


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    media: dict[str, dict[str, float | str]] = {}
    missing = []

    for clip in CLIPS:
        src = RUNWAY / f"{clip}.mp4"
        if not src.is_file():
            missing.append(src.name)
            continue
        shutil.copyfile(src, OUT / src.name)
        media[clip] = {"file": f"ad/{src.name}", "seconds": seconds(src)}

    for key, name in STILLS.items():
        src = RUNWAY / name
        if src.is_file():
            shutil.copyfile(src, OUT / name)
            media[key] = {"file": f"ad/{name}", "seconds": 0}
        else:
            missing.append(name)

    for name in AUDIO:
        src = RUNWAY / f"{name}.wav"
        if not src.is_file():
            missing.append(src.name)
            continue
        normalise(src, OUT / src.name)
        media[name] = {"file": f"ad/{src.name}", "seconds": seconds(OUT / src.name)}

    for name in VOICE_LINES:
        src = VOICES / f"{name}_phone.wav"
        if not src.is_file():
            missing.append(f"voices/{src.name}")
            continue
        shutil.copyfile(src, OUT / f"voice_{name}.wav")
        media[f"voice_{name}"] = {"file": f"ad/voice_{name}.wav", "seconds": seconds(src)}

    manifest = FILM / "src" / "ad-media.json"
    manifest.write_text(json.dumps(media, indent=2) + "\n", encoding="utf-8")
    for key, info in media.items():
        print(f"{key:14} {info['seconds']:.3f}s  {info['file']}")
    if missing:
        print("MISSING:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
