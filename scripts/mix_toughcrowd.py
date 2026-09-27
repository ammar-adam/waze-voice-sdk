"""Build the TOUGH CROWD sound mix sample-accurately from the Remotion config.

    python scripts/mix_toughcrowd.py film/out/tc/mix.wav

Why this exists: Remotion's own audio for this composition came back with
lines 1 to 4 frames late, differently on every render (the audio assets are
picked up a few frames after their Sequence starts). The picture is fine; the
sound is rebuilt here from exactly the same cue list (film/src/toughcrowd.config.ts,
read through esbuild and node) and the same volume rules as the <Sound />
component in film/src/ToughCrowd.tsx: frame-exact starts, the same gains,
fades, loops and trims. Voices are placed untouched (never cut, stretched or
pitched).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
FILM = REPO / "film"
PUB = FILM / "public"
SR = 48000


def config() -> dict:
    tmp = FILM / "out" / "tc" / "cfg.cjs"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npx", "esbuild", "src/toughcrowd.config.ts", "--bundle", "--platform=node", "--format=cjs",
                    f"--outfile={tmp}", "--log-level=error"], cwd=FILM, check=True, shell=sys.platform == "win32")
    keys = "FPS,TOTAL,TAP_LEAD,MIX,BEDS,HITS,MUSIC,END,LINES"
    js = f"const c=require({json.dumps(str(tmp))});const o={{}};for(const k of '{keys}'.split(','))o[k]=c[k];console.log(JSON.stringify(o))"
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def load(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def gain(db: float) -> float:
    return 10 ** (db / 20)


def main() -> int:
    dest = Path(sys.argv[1])
    c = config()
    fps = c["FPS"]
    f = lambda s: round(s * fps)  # noqa: E731  (same rounding as ToughCrowd.tsx)
    spf = SR // fps  # 2000 samples per frame
    total = f(c["TOTAL"]) * spf
    mix = np.zeros((total, 2), np.float32)
    lines = json.loads((FILM / "src" / "toughcrowd-lines.json").read_text(encoding="utf-8"))

    def place(sig: np.ndarray, start_frame: int, env: np.ndarray | float = 1.0) -> None:
        a = start_frame * spf
        n = min(len(sig), total - a)
        if n <= 0:
            return
        e = env[:n, None] if isinstance(env, np.ndarray) else env
        mix[a : a + n] += sig[:n] * e

    def envelope(frames: int, points: list[tuple[float, float]]) -> np.ndarray:
        """Piecewise-linear in frames, like Remotion's interpolate() with clamping."""
        t = np.arange(frames * spf) / spf
        xs, ys = zip(*points)
        return np.interp(t, xs, ys).astype(np.float32)

    # beds: looped, trimmed, faded in and out
    for b in c["BEDS"]:
        dur = f(b["to"]) - f(b["from"])
        src = load(PUB / "tc" / b["src"])
        src = src[f(b.get("offset", 0)) * spf :]
        reps = int(np.ceil(dur * spf / len(src))) + 1
        sig = np.tile(src, (reps, 1))[: dur * spf]
        fi, fo = max(1, f(b.get("fadeIn", 0.04))), max(1, f(b.get("fadeOut", 0.04)))
        env = envelope(dur, [(0, 0), (fi, 1), (dur - fo, 1), (dur, 0)]) * gain(b["db"])
        place(sig, f(b["from"]), env)

    tap = load(PUB / "tc" / "sfx" / "tap.wav")
    for l in c["LINES"]:
        place(tap, f(l["at"] - c["TAP_LEAD"]), gain(c["MIX"]["tapDb"]))
        place(load(PUB / lines[l["key"]]["file"]), f(l["at"]), gain(c["MIX"]["voiceDb"]))
    for h in c["HITS"]:
        place(load(PUB / "tc" / h["src"]), f(h["at"]), gain(h["db"]))
    place(tap, f(c["END"]["filmIn"] + c["END"]["urlAt"]), gain(c["MIX"]["tapDb"]))

    m = c["MUSIC"]
    start = f(m["hitAt"] - m["leadIn"])
    dur = f(c["TOTAL"]) - start
    score = load(PUB / "tc" / m["src"])[f(m["hitInFile"] - m["leadIn"]) * spf :]
    env = envelope(dur, [(0, 0), (3, 1), (dur - f(m["fadeOut"]), 1), (dur - 1, 0), (dur, 0)]) * gain(m["db"])
    place(score[: dur * spf], start, env)

    peak = float(np.abs(mix).max())
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    import wave

    with wave.open(str(dest), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"mix -> {dest} ({total / SR:.3f}s, sample peak {20 * np.log10(peak):.1f} dBFS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
