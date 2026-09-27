"""Build THE GETAWAY sound mix sample-accurately from the Remotion config.

    python scripts/mix_getaway.py film/out/ga/mix.wav

The picture is rendered muted; the sound is built here from exactly the same
cue list (film/src/getaway.config.ts, read through esbuild and node), because
Remotion's own audio placed lines 1 to 4 frames late on the last film. Every
cue starts on its frame to the sample. Voices are placed untouched: never cut,
stretched or pitched.

Units: beds' from/to/fadeIn/fadeOut and every `at` are film frames; a bed's
`offset` is seconds into its (looped) file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
FILM = REPO / "film"
PUB = FILM / "public"
SR = 48000


def config() -> dict:
    tmp = FILM / "out" / "ga" / "cfg.cjs"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "npx",
            "esbuild",
            "src/getaway.config.ts",
            "--bundle",
            "--platform=node",
            "--format=cjs",
            f"--outfile={tmp}",
            "--log-level=error",
        ],
        cwd=FILM,
        check=True,
        shell=sys.platform == "win32",
    )
    keys = "FPS,TOTAL_FRAMES,MIX,BEDS,HITS,TAPS,MUSIC_HIT,LINES"
    js = f"const c=require({json.dumps(str(tmp))});const o={{}};for(const k of '{keys}'.split(','))o[k]=c[k];console.log(JSON.stringify(o))"  # noqa: E501
    return json.loads(
        subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    )


def load(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def gain(db: float) -> float:
    return 10 ** (db / 20)


def main() -> int:
    dest = Path(sys.argv[1])
    c = config()
    spf = SR // c["FPS"]  # 2000 samples per frame
    total = c["TOTAL_FRAMES"] * spf
    mix = np.zeros((total, 2), np.float32)
    lines = json.loads((FILM / "src" / "getaway-lines.json").read_text(encoding="utf-8"))

    def place(sig: np.ndarray, frame: int, env: np.ndarray | float = 1.0) -> None:
        a = frame * spf
        n = min(len(sig), total - a)
        if n <= 0:
            return
        e = env[:n, None] if isinstance(env, np.ndarray) else env
        mix[a : a + n] += sig[:n] * e

    def envelope(frames: int, points: list[tuple[float, float]]) -> np.ndarray:
        t = np.arange(frames * spf) / spf
        xs, ys = zip(*points, strict=True)
        return np.interp(t, xs, ys).astype(np.float32)

    for b in c["BEDS"]:
        dur = b["to"] - b["from"]
        src = load(PUB / "ga" / b["src"])
        src = src[int(b.get("offset", 0) * SR) :]
        reps = int(np.ceil(dur * spf / len(src))) + 1
        sig = np.tile(src, (reps, 1))[: dur * spf]
        fi, fo = max(1, b.get("fadeIn", 1)), max(1, b.get("fadeOut", 1))
        env = envelope(dur, [(0, 0), (fi, 1), (dur - fo, 1), (dur, 0)]) * gain(b["db"])
        place(sig, b["from"], env)

    tap = load(PUB / "ga" / "sfx" / "tap.wav")
    for at in c["TAPS"]:
        place(tap, at, gain(c["MIX"]["tapDb"]))
    for h in c["HITS"]:
        place(load(PUB / "ga" / h["src"])[int(h.get("offset", 0) * SR) :], h["at"], gain(h["db"]))
    m = c["MUSIC_HIT"]
    hit = load(PUB / "ga" / m["src"])
    # the hit rings to the last frame and fades to silence exactly there
    room = total - m["at"] * spf
    hit = hit[:room]
    fade = np.ones(len(hit), np.float32)
    k = min(len(hit), int(0.6 * SR))
    fade[-k:] = np.linspace(1, 0, k)
    place(hit * fade[:, None], m["at"], gain(m["db"]))
    for line in c["LINES"]:
        place(load(PUB / lines[line["key"]]["file"]), line["at"], gain(c["MIX"]["voiceDb"]))

    peak = float(np.abs(mix).max())
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"mix -> {dest} ({total / SR:.3f}s, sample peak {20 * np.log10(peak):.1f} dBFS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
