"""Stage THE GETAWAY media into film/public/ga/ (git-ignored) for Remotion.

    python scripts/stage_getaway.py

- footage: the reused takes in film/runway3/takes/ -> public/ga/clips/<name>.mp4;
  the NEW action shots from film/runway4/takes/ when a take exists, otherwise
  the approved first frame (film/runway4/stills/<N>_first.png, from
  scripts/prep_getaway_frames.py) held for 8 s as a placeholder; which is
  which goes to film/src/getaway-media.json, and the picture pushes in on a
  placeholder
- sound: SFX from film/runway3/sfx/ and the earlier films, loudness-matched;
  the drone, the screen tap and the music hit are synthesised here
- faces: site/faces/*.svg -> public/ga/faces/; film grain
- words: the voice JSONs written by build_getaway_voices.py become
  film/src/getaway-lines.json (text from the presets, one entry per preset
  word, timings from faster-whisper on the treated file, each phrase's first
  word pulled to the measured speech onset).

Run scripts/build_getaway_voices.py first.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
R3 = REPO / "film" / "runway3"
R4 = REPO / "film" / "runway4"
PUB = REPO / "film" / "public" / "ga"
SR = 48000

# Reused from the first cut (film/runway3/takes/).
CLIPS = {
    "V02A": "V02_chain_a.mp4",
    "V02B": "V02_chain_b.mp4",
    "V03": "V03_rack_a.mp4",
    "V05": "V05_tyre_a.mp4",
    "V08": "V08_natural_a.mp4",
    "V09": "V09_officer_a.mp4",
    "V12": "V12_smirk_a.mp4",
    "V13": "V13_garage_a.mp4",
}
# The NEW action shots (film/runway4/plan.md): the kept take, by name, in film/runway4/takes/.
NEW = {
    "N1": "N1_a.mp4",
    "N2": "N2_a.mp4",
    "N3": "N3_a.mp4",
    "N4": "N4_a.mp4",
    "N5": "N5_a.mp4",
    "N6": "N6_a.mp4",
    "N7": "N7_a.mp4",
}

# name -> (source, integrated loudness to stage at). Beds loop seamlessly (forward then back).
BEDS = {
    "alarm_rain": (R3 / "sfx" / "alarm_rain.mp3", -20),
    "rain_roof": (R3 / "sfx" / "rain_roof.mp3", -20),
    "sirens": (R3 / "sfx" / "sirens.mp3", -20),
    "road": (REPO / "film" / "runway2" / "sfx" / "road.mp3", -20),
}
ONE_SHOTS = {
    "peel_out": R3 / "sfx" / "peel_out.mp3",
    "pull_up": R3 / "sfx" / "pull_up.mp3",
    "garage_stop": R3 / "sfx" / "garage_stop.mp3",
    "exhale": R3 / "sfx" / "exhale.mp3",
    "door_thunk": REPO / "film" / "runway2" / "sfx" / "door_thunk.mp3",
    "whoosh": REPO / "film" / "runway2" / "sfx" / "whoosh.mp3",
}


def write_wav(path: Path, x: np.ndarray) -> None:
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def lp(x: np.ndarray, fc: float) -> np.ndarray:
    """One-pole low-pass (vectorised enough for a few seconds of audio)."""
    from scipy.signal import lfilter

    a = np.exp(-2 * np.pi * fc / SR)
    return lfilter([1 - a], [1, -a], x)


def make_tap(dest: Path) -> None:
    """A soft, dry screen tap: a 4 ms click of band-limited noise over a tiny low thock."""
    t = np.arange(int(SR * 0.12)) / SR
    rng = np.random.default_rng(3)
    click = rng.normal(0, 1, t.size) * np.exp(-t / 0.004)
    click = lp(click, 6000) - lp(click, 1200)
    thock = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.018) * 0.5
    x = click / np.abs(click).max() * 0.8 + thock
    write_wav(dest, x / np.abs(x).max() * 0.7)


def make_drone(dest: Path, seconds: float = 4.0) -> None:
    """A dark tension drone: detuned low sines, a slow 1.1 Hz pulse, filtered air."""
    t = np.arange(int(SR * seconds)) / SR
    rng = np.random.default_rng(7)
    base = sum(
        a * np.sin(2 * np.pi * f * t + p)
        for f, a, p in [
            (43.65, 1.0, 0),
            (44.1, 0.8, 1),
            (65.4, 0.45, 2),
            (87.3, 0.25, 0.5),
            (130.8, 0.12, 1.3),
        ]
    )
    pulse = 0.7 + 0.3 * np.sin(2 * np.pi * 1.1 * t - np.pi / 2) ** 2
    air = lp(lp(rng.normal(0, 1, t.size), 900), 900)
    air = air / np.abs(air).max()
    swell = np.clip(t / 1.2, 0, 1) * (0.85 + 0.15 * t / seconds)
    x = (base / 2.6 * pulse + 0.18 * air) * swell
    left = x
    right = np.roll(x, 240)
    write_wav(dest, np.stack([left, right], 1) / np.abs(x).max() * 0.8)


def make_hit(dest: Path, seconds: float = 2.8) -> None:
    """One trailer music hit: a pitched sub drop, a low brass-like chord stab and a dark tail."""
    t = np.arange(int(SR * seconds)) / SR
    rng = np.random.default_rng(11)
    f = 58 * np.exp(-t / 0.35) + 34
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9)
    chord = sum(
        np.sin(2 * np.pi * fr * t)
        + 0.5 * np.sin(4 * np.pi * fr * t)
        + 0.25 * np.sin(6 * np.pi * fr * t)
        for fr in (73.4, 110.0, 146.8, 174.6)
    )
    chord = lp(chord, 1400) * np.exp(-t / 0.7) * np.clip(t / 0.006, 0, 1)
    crack = lp(rng.normal(0, 1, t.size), 3500) * np.exp(-t / 0.05)
    tail = lp(lp(rng.normal(0, 1, t.size), 500), 500) * np.exp(-t / 1.1)
    x = (
        1.0 * sub
        + 0.22 * chord / np.abs(chord).max()
        + 0.25 * crack
        + 0.9 * tail / np.abs(tail).max() * 0.4
    )
    fade = np.clip((seconds - t) / 0.4, 0, 1)
    x = x * fade
    write_wav(dest, np.stack([x, np.roll(x, 180)], 1) / np.abs(x).max() * 0.9)


def make_grain(dest: Path) -> None:
    from PIL import Image

    rng = np.random.default_rng(5)
    g = rng.normal(128, 38, (512, 512)).clip(0, 255).astype(np.uint8)
    Image.fromarray(g, "L").convert("RGB").save(dest)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def onsets(path: Path) -> list[float]:
    """Starts of speech phrases in the untreated line: RMS above peak - 30 dB
    after >= 0.12 s of quiet, lasting >= 0.15 s (breaths and clicks are skipped)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    x = np.frombuffer(raw, np.float32)
    hop = SR // 100
    n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    act = np.where(db > db.max() - 30)[0]
    segs, s0, prev = [], act[0], act[0]
    for i in act[1:]:
        if i - prev > 12:
            segs.append((s0, prev))
            s0 = i
        prev = i
    segs.append((s0, prev))
    return [a / 100 for a, b in segs if b - a >= 15]


def main() -> int:
    for sub in ("clips", "sfx", "faces"):
        (PUB / sub).mkdir(parents=True, exist_ok=True)
    for name, src in CLIPS.items():
        p = R3 / "takes" / src
        if p.is_file():
            shutil.copy2(p, PUB / "clips" / f"{name}.mp4")
        else:
            print(f"missing clip {name}: {p}")
    media = {}
    for name, take in NEW.items():
        p = R4 / "takes" / take
        if p.is_file():
            shutil.copy2(p, PUB / "clips" / f"{name}.mp4")
            media[name] = "take"
            continue
        still = R4 / "stills" / f"{name}_first.png"
        if not still.is_file():
            print(f"missing NEW shot {name}: no take ({p.name}) and no still ({still.name})")
            return 1
        ffmpeg("-loop", "1", "-framerate", "24", "-i", str(still), "-t", "8", "-vf", "format=yuv420p",
               "-c:v", "libx264", "-crf", "14", "-r", "24", str(PUB / "clips" / f"{name}.mp4"))  # fmt: skip
        media[name] = "placeholder"
    (REPO / "film" / "src" / "getaway-media.json").write_text(
        json.dumps(media, indent=1) + "\n", encoding="utf-8"
    )
    print("NEW shots: " + ", ".join(f"{k} {v}" for k, v in media.items()))
    for name, (src, lufs) in BEDS.items():
        if not src.is_file():
            print(f"missing bed {name}: {src}")
            continue
        ffmpeg(
            "-i",
            str(src),
            "-filter_complex",
            "[0:a]asplit[a][b];[b]areverse[r];[a][r]concat=n=2:v=0:a=1,"
            f"loudnorm=I={lufs}:TP=-3:LRA=11,aresample={SR}",
            "-ac",
            "2",
            str(PUB / "sfx" / f"{name}.wav"),
        )
    for name, src in ONE_SHOTS.items():
        if not src.is_file():
            print(f"missing one-shot {name}: {src}")
            continue
        ffmpeg(
            "-i",
            str(src),
            "-af",
            f"loudnorm=I=-16:TP=-3,aresample={SR}",
            "-ac",
            "2",
            str(PUB / "sfx" / f"{name}.wav"),
        )
    make_tap(PUB / "sfx" / "tap.wav")
    make_drone(PUB / "sfx" / "drone_raw.wav")
    ffmpeg(
        "-i",
        str(PUB / "sfx" / "drone_raw.wav"),
        "-af",
        f"loudnorm=I=-20:TP=-3,aresample={SR}",
        "-ac",
        "2",
        str(PUB / "sfx" / "drone.wav"),
    )
    make_hit(PUB / "sfx" / "hit_raw.wav")
    ffmpeg(
        "-i",
        str(PUB / "sfx" / "hit_raw.wav"),
        "-af",
        f"loudnorm=I=-14:TP=-2,aresample={SR}",
        "-ac",
        "2",
        str(PUB / "sfx" / "hit.wav"),
    )
    make_grain(PUB / "grain.png")
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
        # Whisper's word starts can trail the audible onset; snap each phrase's
        # first word to the measured onset when that is within 0.3 s earlier.
        # The phrase's first word is the one starting nearest the onset (from
        # 0.1 s before it); only a late start is moved, never a later word.
        heard = [dict(h) for h in heard]
        for on in onsets(PUB / "voices" / f"{j.stem}_clean.wav"):
            near = [h for h in heard if -0.1 <= h["start"] - on <= 0.3]
            if near:
                h = min(near, key=lambda h: abs(h["start"] - on))
                if h["start"] > on:
                    h["start"] = round(on, 2)
        lines[j.stem] = {
            "file": f"ga/voices/{j.stem}.wav",
            "pack": info["pack"],
            "phrase_id": info["phrase_id"],
            "text": info["text"],
            "seconds": info["seconds"],
            "words": [
                {"w": w, "start": h["start"], "end": h["end"]}
                for w, h in zip(words, heard, strict=False)
            ],
        }
    out = REPO / "film" / "src" / "getaway-lines.json"
    out.write_text(json.dumps(lines, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"staged {len(CLIPS) + len(NEW)} clips, {len(lines)} lines -> {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
