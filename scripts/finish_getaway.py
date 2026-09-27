"""Render and master both cuts of THE GETAWAY.

    python scripts/finish_getaway.py             # render + mix + master both
    python scripts/finish_getaway.py --no-render # mix + master the existing raw renders
    python scripts/finish_getaway.py --only 9x16 # one cut only (the other master is left untouched)

1. Renders Getaway (1920x1080) and GetawayVertical (1080x1920) muted into
   film/out/ga/raw_*.mp4 (--concurrency=2).
2. Builds the sound once with scripts/mix_getaway.py from the same cue list.
3. Checks every voice line in the mix by cross-correlating it with its source
   file: each must start on its planned frame (under half a frame off).
4. Converts the picture to limited-range yuv420p (Remotion writes full-range
   yuvj420p), masters with scripts/master_ad.py (-14 LUFS, true peak under
   -1 dBTP, AAC 320k) into film/out/getaway_16x9.mp4 and _9x16.mp4, re-checks
   the line sync, and writes web copies (H.264 about 10 Mbps, faststart) as
   film/out/getaway_16x9_web.mp4 and _9x16_web.mp4.
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
CUTS = {"16x9": "Getaway", "9x16": "GetawayVertical"}


def plan() -> list[tuple[str, float]]:
    """(voice key, planned start in seconds) for every line, from the config itself."""
    tmp = OUT / "ga" / "cfg.cjs"
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
    js = f"const c=require({json.dumps(str(tmp))});console.log(JSON.stringify(c.LINES.map(l=>[l.key,l.at/c.FPS])))"  # noqa: E501
    return json.loads(
        subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    )


def pcm(path: Path | str, sr: int = 16000) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)


def offsets(path: Path, lines: list[tuple[str, float]]) -> list[float]:
    """Seconds each line sits late (+) or early (-) of its planned frame."""
    mix = pcm(path)
    out = []
    for key, at in lines:
        voice = pcm(FILM / "public" / "ga" / "voices" / f"{key}.wav")
        a = max(0, int((at - 0.3) * 16000))
        seg = mix[a : a + len(voice) + int(0.6 * 16000)]
        c = np.correlate(seg, voice, "valid")
        out.append((a + int(np.argmax(np.abs(c)))) / 16000 - at)
    return out


def main() -> int:
    render = "--no-render" not in sys.argv
    cuts = CUTS
    if "--only" in sys.argv:
        tag = sys.argv[sys.argv.index("--only") + 1]
        cuts = {tag: CUTS[tag]}
    (OUT / "ga").mkdir(parents=True, exist_ok=True)
    lines = plan()
    raws = {tag: OUT / "ga" / f"raw_{tag}.mp4" for tag in cuts}
    if render:
        for tag, comp in cuts.items():
            subprocess.run(
                ["npx", "remotion", "render", comp, str(raws[tag]), "--concurrency=2", "--crf=12", "--muted", "--log=error"],  # noqa: E501
                cwd=FILM, check=True, shell=sys.platform == "win32",
            )  # fmt: skip
    mix = OUT / "ga" / "mix.wav"
    subprocess.run([PY, str(REPO / "scripts" / "mix_getaway.py"), str(mix)], check=True)
    offs = offsets(mix, lines)
    print(f"mix: line offsets (ms) {[round(o * 1000, 1) for o in offs]}")
    if max(abs(o) for o in offs) >= 1 / 48:
        print("the mix is not frame-accurate; stopping")
        return 1
    for tag in cuts:
        fixed = OUT / "ga" / f"fixed_{tag}.mov"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(raws[tag]), "-i", str(mix), "-map", "0:v", "-map", "1:a",  # noqa: E501
             "-vf", "scale=in_range=full:out_range=tv,format=yuv420p", "-color_range", "tv",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "14", "-r", "24",
             "-af", "apad", "-shortest", "-c:a", "pcm_s24le", str(fixed)],
            check=True,
        )  # fmt: skip
        dest = OUT / f"getaway_{tag}.mp4"
        subprocess.run(
            [
                PY,
                str(REPO / "scripts" / "master_ad.py"),
                str(fixed),
                str(dest),
                "--bitrate",
                "320k",
            ],
            check=True,
        )
        offs = offsets(dest, lines)
        print(
            f"{tag}: mastered -> {dest.relative_to(REPO)}; lines {[round(o * 1000) for o in offs]} ms from their frames"  # noqa: E501
        )
        web = OUT / f"getaway_{tag}_web.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(dest), "-c:v", "libx264", "-profile:v", "high", "-preset", "slow",  # noqa: E501
             "-b:v", "10M", "-maxrate", "12M", "-bufsize", "20M", "-pix_fmt", "yuv420p", "-r", "24",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(web)],
            check=True,
        )  # fmt: skip
        print(f"{tag}: web copy -> {web.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
