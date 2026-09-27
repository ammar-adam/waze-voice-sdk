"""Render and master both cuts of TOUGH CROWD.

    python scripts/finish_toughcrowd.py            # render + master both
    python scripts/finish_toughcrowd.py --no-render  # master existing raw renders

1. Renders ToughCrowd (1920x1080) and ToughCrowdVertical (1080x1920) with
   Remotion, muted, into film/out/tc/raw_*.mp4.
2. Builds the sound once with scripts/mix_toughcrowd.py from the same cue
   list (Remotion's own audio put lines 1 to 4 frames late, differently on
   every render, even as WAV). Both cuts share this one mix.
3. Checks every voice line in the mix by cross-correlating it with the
   line's source file: each must sit on its planned frame.
4. Converts the picture to limited-range yuv420p (Remotion writes
   full-range yuvj420p) and masters with scripts/master_ad.py (-14 LUFS, true peak under -1 dBTP,
   AAC 320 kbps) into film/out/tough_crowd_16x9.mp4 and _9x16.mp4.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
FILM = REPO / "film"
OUT = FILM / "out"
PY = sys.executable
CUTS = {"16x9": "ToughCrowd", "9x16": "ToughCrowdVertical"}


def lines() -> list[tuple[str, float]]:
    """(voice key, start time on its whole frame) for every line, from the config itself."""
    tmp = OUT / "tc" / "cfg.cjs"
    subprocess.run(["npx", "esbuild", "src/toughcrowd.config.ts", "--bundle", "--platform=node", "--format=cjs",
                    f"--outfile={tmp}", "--log-level=error"], cwd=FILM, check=True, shell=sys.platform == "win32")
    js = f"const c=require({json.dumps(str(tmp))});console.log(JSON.stringify(c.LINES.map(l=>[l.key,Math.round(l.at*24)/24])))"
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)


def pcm(path: Path | str, sr: int = 48000, start: float = 0, dur: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path)]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)


def offsets(path: Path, plan: list[tuple[str, float]]) -> list[float]:
    """Seconds each line sits late (+) or early (-) of its planned frame."""
    mix = pcm(path, sr=16000)
    out = []
    for key, at in plan:
        voice = pcm(FILM / "public" / "tc" / "voices" / f"{key}.wav", sr=16000)
        a = max(0, int((at - 0.3) * 16000))
        seg = mix[a : a + len(voice) + int(0.9 * 16000)]
        c = np.correlate(seg, voice, "valid")
        out.append((a + int(np.argmax(np.abs(c)))) / 16000 - at)
    return out


def main() -> int:
    render = "--no-render" not in sys.argv
    (OUT / "tc").mkdir(parents=True, exist_ok=True)
    plan = lines()
    raws = {tag: OUT / "tc" / f"raw_{tag}.mp4" for tag in CUTS}
    mix = OUT / "tc" / "mix.wav"
    if render:
        # Picture only: Remotion's sound for this composition put lines 1 to 4
        # frames late, differently on every render. The mix is built instead by
        # scripts/mix_toughcrowd.py from the same cue list, sample-accurately.
        for tag, comp in CUTS.items():
            subprocess.run(
                ["npx", "remotion", "render", comp, str(raws[tag]), "--concurrency=2", "--crf=14", "--muted", "--log=error"],
                cwd=FILM, check=True, shell=sys.platform == "win32",
            )  # fmt: skip
    subprocess.run([PY, str(REPO / "scripts" / "mix_toughcrowd.py"), str(mix)], check=True)
    offs = offsets(mix, plan)
    spread = max(offs) - min(offs)
    print(f"mix: line offsets (ms) {[round(o * 1000, 1) for o in offs]}; spread {spread * 1000:.1f} ms")
    if spread >= 1 / 48 or max(abs(o) for o in offs) >= 1 / 24:
        print("the mix is not frame-accurate; stopping")
        return 1
    src = mix
    print(f"sound from {src.name}")
    for tag in CUTS:
        fixed = OUT / "tc" / f"fixed_{tag}.mov"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(raws[tag]), "-i", str(src), "-map", "0:v", "-map", "1:a",
             "-vf", "scale=in_range=full:out_range=tv,format=yuv420p", "-color_range", "tv",
             "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "14", "-r", "24",
             "-af", "apad",
             "-shortest", "-c:a", "pcm_s24le", str(fixed)],
            check=True,
        )  # fmt: skip
        dest = OUT / f"tough_crowd_{tag}.mp4"
        subprocess.run([PY, str(REPO / "scripts" / "master_ad.py"), str(fixed), str(dest), "--bitrate", "320k"], check=True)
        offs = offsets(dest, plan)
        print(f"{tag}: mastered -> {dest.relative_to(REPO)}; lines now {[round(o * 1000) for o in offs]} ms from their frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
