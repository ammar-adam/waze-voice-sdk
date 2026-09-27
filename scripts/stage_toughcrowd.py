"""Stage the Tough Crowd media into film/public/tc/ (git-ignored) for Remotion.

    python scripts/stage_toughcrowd.py

- footage: the kept takes in film/runway2/takes/ and tests/ -> public/tc/clips/
- sound: sfx from film/runway2/sfx/ (and the film/runway/ fallbacks), the score
- faces: site/faces/*.svg -> public/tc/faces/
- words: the voice JSONs written by build_toughcrowd_voices.py are merged into
  film/src/toughcrowd-lines.json, which the captions read (text from the
  presets, timings from faster-whisper on the treated file).

Run scripts/build_toughcrowd_voices.py first.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
R2 = REPO / "film" / "runway2"
PUB = REPO / "film" / "public" / "tc"

CLIPS = {
    "S01": R2 / "takes" / "S01_a.mp4",
    "S02": R2 / "takes" / "S02_a.mp4",
    "S03": R2 / "takes" / "S03_a.mp4",
    "S04": R2 / "takes" / "S04_a.mp4",
    "S05": R2 / "takes" / "S05_a.mp4",
    "S06": R2 / "takes" / "S06_b.mp4",
    "S06A": R2 / "takes" / "S06_a.mp4",
    "S08": R2 / "takes" / "S08_a.mp4",
    "S09": R2 / "tests" / "T2_S09_donkey_veo8.mp4",
    "S10": R2 / "takes" / "S10_a.mp4",
    "S11": R2 / "tests" / "T1_S13_payoff_veo8.mp4",
    "S13": R2 / "takes" / "S13_a.mp4",
}
SOUNDS = {
    "score.wav": REPO / "film" / "runway" / "score.wav",
    "sfx_truck.wav": REPO / "film" / "runway" / "sfx_truck.wav",
    "sfx_dusk.wav": REPO / "film" / "runway" / "sfx_dusk.wav",
}


# name -> integrated loudness to stage at. Room tone is near-silence by design.
BEDS = {"morning_street": -20, "cab_idle": -20, "road": -20, "town_street": -20, "room_tone": -38}
ONE_SHOTS = ["door_thunk", "whoosh"]


def make_tap(dest: Path) -> None:
    """A soft, dry screen tap: a 4 ms click of band-limited noise over a tiny low thock.

    The generated phone_tap.mp3 came back almost silent (-68 dB), so the tap is
    synthesised instead."""
    import numpy as np

    sr = 48000
    t = np.arange(int(sr * 0.12)) / sr
    rng = np.random.default_rng(3)
    click = rng.normal(0, 1, t.size) * np.exp(-t / 0.004)
    # crude band-pass: difference of two one-pole low-passes
    def lp(x, fc):
        a = np.exp(-2 * np.pi * fc / sr)
        y = np.zeros_like(x)
        for i in range(1, x.size):
            y[i] = (1 - a) * x[i] + a * y[i - 1]
        return y
    click = lp(click, 6000) - lp(click, 1200)
    thock = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.018) * 0.5
    x = click / np.abs(click).max() * 0.8 + thock
    x = x / np.abs(x).max() * 0.7
    pcm = (np.stack([x, x], 1) * 32767).astype("<i2").tobytes()
    import wave

    with wave.open(str(dest), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def main() -> int:
    for sub in ("clips", "sfx", "faces"):
        (PUB / sub).mkdir(parents=True, exist_ok=True)
    for name, src in CLIPS.items():
        if src.is_file():
            shutil.copy2(src, PUB / "clips" / f"{name}.mp4")
        else:
            print(f"missing clip {name}: {src}")
    # B7 (Vader): take A's micro-smile, played forward to its first 4 frames and
    # back again, so it flickers and is clamped down (take A's full grin after
    # src 4.3s is never used). Frames 12..102 forward, then 101..85 reversed.
    # The smile starts at src frame 98, so it peaks 90 frames into the shot.
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(CLIPS["S06A"]), "-filter_complex",
         "[0:v]trim=start_frame=12:end_frame=103,setpts=PTS-STARTPTS[a];"
         "[0:v]trim=start_frame=85:end_frame=102,setpts=PTS-STARTPTS,reverse[b];"
         "[a][b]concat=n=2:v=1:a=0,format=yuv420p",
         "-r", "24", "-c:v", "libx264", "-crf", "10", "-preset", "slow", str(PUB / "clips" / "S06V.mp4")],
        check=True,
    )  # fmt: skip
    for name, src in SOUNDS.items():
        shutil.copy2(src, PUB / name)
    # Beds: made seamless (played forward then backward, so a loop never clicks)
    # and loudness-matched (-20 LUFS, room tone -38); the mix in toughcrowd.config.ts sets
    # each one relative to that. One-shots: peak-normalised to -3 dBFS.
    for name, lufs in BEDS.items():
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(R2 / "sfx" / f"{name}.mp3"),
             "-filter_complex", "[0:a]asplit[a][b];[b]areverse[r];[a][r]concat=n=2:v=0:a=1,"
             f"loudnorm=I={lufs}:TP=-3:LRA=11,aresample=48000",
             "-ac", "2", str(PUB / "sfx" / f"{name}.wav")],
            check=True,
        )  # fmt: skip
    for name in ONE_SHOTS:
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(R2 / "sfx" / f"{name}.mp3"),
             "-af", "loudnorm=I=-16:TP=-3,aresample=48000", "-ac", "2", str(PUB / "sfx" / f"{name}.wav")],
            check=True,
        )  # fmt: skip
    make_tap(PUB / "sfx" / "tap.wav")
    for src in sorted((REPO / "site" / "faces").glob("*.svg")):
        shutil.copy2(src, PUB / "faces" / src.name)

    lines = {}
    for j in sorted((PUB / "voices").glob("*.json")):
        info = json.loads(j.read_text(encoding="utf-8"))
        words = info["text"].split()
        heard = info["words"]
        if len(words) != len(heard):
            print(f"{j.stem}: {len(words)} preset words vs {len(heard)} heard; fix the mapping")
            return 1
        lines[j.stem] = {
            "file": f"tc/voices/{j.stem}.wav",
            "pack": info["pack"],
            "phrase_id": info["phrase_id"],
            "text": info["text"],
            "seconds": info["seconds"],
            "words": [{"w": w, "start": h["start"], "end": h["end"]} for w, h in zip(words, heard)],
        }
    out = REPO / "film" / "src" / "toughcrowd-lines.json"
    out.write_text(json.dumps(lines, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"staged {len(CLIPS)} clips, {len(lines)} lines -> {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
