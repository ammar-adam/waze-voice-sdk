"""Export the eight Tough Crowd voice lines from the live packs' master audio.

Same treatment as scripts/build_ad_voices.py (the phone on the dash): trim the
silence at each end, band-limit, a touch of small-room reverb, loudness-match
to -16 LUFS. Vader keeps his low end (high-pass at 180 Hz instead of 250 Hz).
Never cut, speed up or pitch-shift a voice: the trim only removes silence
below -45 dB at the ends.

Writes film/public/tc/voices/<name>.wav plus <name>.json with the measured
duration and the faster-whisper word timings of the treated file, which the
Remotion captions read.

    python scripts/build_toughcrowd_voices.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "film" / "public" / "tc" / "voices"

# name -> (pack, phrase id, high-pass Hz)
LINES = {
    "elmo_hook": ("elmo", "start_drive_7", 250),
    "ramsay_traffic": ("gordon-ramsay", "traffic_ahead", 250),
    "pooh_traffic": ("pooh", "traffic_ahead", 250),
    "cartman_traffic": ("eric-cartman", "traffic_ahead", 250),
    "vader_traffic": ("darth-vader", "traffic_ahead", 180),
    "ramsay_donkey": ("gordon-ramsay", "reroute_chime", 250),
    "bugs_arrived": ("bugs-bunny", "arrived", 250),
    "elmo_payoff": ("elmo", "start_drive_1", 250),
}

TRIM = (
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse"
)


def phone(hp: int) -> str:
    return (
        f"highpass=f={hp},highpass=f={hp},lowpass=f=7000,lowpass=f=7000,"
        "aecho=0.85:0.6:14|27:0.12|0.07,loudnorm=I=-16:TP=-2:LRA=7"
    )


def seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return float(out.stdout.strip())


def main() -> int:
    from faster_whisper import WhisperModel

    OUT.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    for name, (pack, phrase, hp) in LINES.items():
        src = REPO / "packs" / pack / "audio" / "master" / f"{phrase}.mp3"
        text = json.loads((REPO / "presets" / f"{pack}.json").read_text(encoding="utf-8"))["lines"][phrase]
        clean = OUT / f"{name}_clean.wav"
        dest = OUT / f"{name}.wav"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src),
             "-af", f"{TRIM},aresample=48000", "-ac", "1", str(clean)],
            check=True,
        )  # fmt: skip
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(clean),
             "-af", f"{phone(hp)},aresample=48000", "-ac", "1", str(dest)],
            check=True,
        )  # fmt: skip
        segs, _ = model.transcribe(str(clean), word_timestamps=True, beam_size=5)
        words = [
            {"w": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
            for s in segs
            for w in s.words
        ]
        info = {
            "pack": pack,
            "phrase_id": phrase,
            "text": text,
            "transcript": " ".join(w["w"] for w in words),
            "source_seconds": round(seconds(src), 3),
            "seconds": round(seconds(dest), 3),
            "words": words,
        }
        (OUT / f"{name}.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
        print(f"{name:16} {info['seconds']:.2f}s  {text!r}  heard: {info['transcript']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
