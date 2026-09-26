"""Cut the 30s ad's four voice lines from the live packs.

Taken from each pack's master audio, not the exported pack: the pack is
squeezed to a low bitrate to fit Waze's size cap, and the ad deserves the
source. Two-part lines are joined back to back, exactly as Waze plays them.
Leading and trailing silence is trimmed; nothing else is touched in the clean
file. Never cut, speed up or pitch-shift a voice.

A second file, <name>_phone.wav, is the same line as if from a phone on the
dash: band-limited 250 Hz to 7 kHz, a touch of small-room reverb, and
loudness-matched to -16 LUFS so the lines sit at one level in the mix.

    python scripts/build_ad_voices.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "film" / "voices"

# ad name -> (pack, [phrase ids in order])
LINES = {
    "pooh": ("pooh", ["in_quarter_mile", "turn_right"]),
    "batman": ("batman", ["reroute_chime"]),
    "elmo": ("elmo", ["arrived"]),
    "cookie": ("cookie-monster", ["in_quarter_mile", "turn_right"]),
}

TRIM = (
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse"
)
PHONE = (
    "highpass=f=250,highpass=f=250,lowpass=f=7000,lowpass=f=7000,"
    "aecho=0.85:0.6:14|27:0.12|0.07,loudnorm=I=-16:TP=-2:LRA=7"
)


def seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (pack, phrase_ids) in LINES.items():
        sources = [REPO / "packs" / pack / "audio" / "master" / f"{p}.mp3" for p in phrase_ids]
        missing = [s for s in sources if not s.is_file()]
        if missing:
            print(f"missing {missing[0]}: build the pack first")
            return 1
        inputs = [arg for s in sources for arg in ("-i", str(s))]
        joined = f"concat=n={len(sources)}:v=0:a=1," if len(sources) > 1 else ""
        clean = OUT / f"{name}.wav"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", *inputs,
             "-filter_complex", f"{joined}{TRIM},aresample=48000", "-ac", "1", str(clean)],
            check=True,
        )  # fmt: skip
        phone = OUT / f"{name}_phone.wav"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(clean),
             "-af", f"{PHONE},aresample=48000", "-ac", "1", str(phone)],
            check=True,
        )  # fmt: skip
        print(f"{name:8} {seconds(clean):.2f}s  {' + '.join(phrase_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
