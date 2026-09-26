"""Make every prompt in a pack sound like the same person.

A community model does not give the same performance twice: one take is warm,
the next is flat, a third sounds like a different person. On a drive that
reads as three characters sharing one pack.

This fingerprints every synthesized clip on timbre (mean log-mel spectrum,
level removed), pitch, pitch range (a flat read has a narrow one) and
brightness, and measures each against an anchor: a take someone has judged
right, or failing that the pack's most typical clip. Outliers are regenerated
several times and the take closest to the anchor is kept.

    python scripts/voice_consistency.py hagrid --anchor-phrase arrived
    python scripts/voice_consistency.py batman --fix --takes 3

After --fix, rebuild with --reuse so the kept takes flow through to the pack:
    python scripts/build_all.py --only hagrid --no-stage --reuse
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from build_all import FISH_VOICES  # noqa: E402

from waze_voice import phrases, presets, providers  # noqa: E402

SR = 16000


def pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(SR),
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def _mel_bank(n_fft: int, bands: int = 40, lo: float = 60.0, hi: float = 7000.0) -> np.ndarray:
    def mel(f: np.ndarray) -> np.ndarray:
        return 2595 * np.log10(1 + f / 700)

    edges = 700 * (10 ** (np.linspace(mel(np.array(lo)), mel(np.array(hi)), bands + 2) / 2595) - 1)
    freqs = np.fft.rfftfreq(n_fft, 1 / SR)
    bank = np.zeros((bands, len(freqs)))
    for b in range(bands):
        left, centre, right = edges[b], edges[b + 1], edges[b + 2]
        rise = (freqs - left) / (centre - left)
        fall = (right - freqs) / (right - centre)
        bank[b] = np.clip(np.minimum(rise, fall), 0, None)
    return bank


BANK = _mel_bank(1024)


def fingerprint(path: Path) -> dict[str, np.ndarray | float]:
    x = pcm(path)
    frames = np.lib.stride_tricks.sliding_window_view(x, 1024)[::256] * np.hanning(1024)
    power = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    energy = power.sum(axis=1)
    voiced = energy > np.percentile(energy, 40)
    logmel = np.log(power[voiced] @ BANK.T + 1e-9)
    timbre = logmel.mean(axis=0)
    timbre -= timbre.mean()
    freqs = np.fft.rfftfreq(1024, 1 / SR)
    centroid = float((power[voiced] @ freqs).sum() / (power[voiced].sum() + 1e-9))
    f0s = []
    for fr in frames[voiced]:
        ac = np.correlate(fr, fr, "full")[1023:]
        lo, hi = SR // 400, SR // 60
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.3 * ac[0]:
            f0s.append(SR / lag)
    f0 = np.log(np.array(f0s)) if f0s else np.log(np.array([100.0]))
    return {
        "timbre": timbre,
        "pitch": float(np.median(f0)),
        "range": float(np.std(f0)),
        "bright": np.log(centroid),
    }


def distance(a: dict, b: dict) -> float:
    cos = float(
        np.dot(a["timbre"], b["timbre"])
        / (np.linalg.norm(a["timbre"]) * np.linalg.norm(b["timbre"]))
    )
    return (
        (1 - cos) * 10
        + abs(a["pitch"] - b["pitch"]) * 3
        + abs(a["range"] - b["range"]) * 4
        + abs(a["bright"] - b["bright"]) * 2
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack")
    parser.add_argument("--anchor", type=Path, help="An audio file judged to be the right voice.")
    parser.add_argument(
        "--anchor-phrase", help="A phrase id in this pack whose take is the reference."
    )
    parser.add_argument(
        "--fix", action="store_true", help="Regenerate outliers, keep the closest take."
    )
    parser.add_argument("--takes", type=int, default=3)
    parser.add_argument(
        "--also", action="append", default=[], help="Phrase ids to re-take regardless."
    )
    parser.add_argument(
        "--threshold", type=float, default=2.0, help="Outlier cut, in MADs above the median."
    )
    args = parser.parse_args(argv)

    synth = REPO / "packs" / args.pack / "audio" / "synthesized"
    clips = {p.stem: p for p in sorted(synth.glob("*.mp3"))}
    prints = {k: fingerprint(p) for k, p in clips.items()}

    if args.anchor:
        anchor = fingerprint(args.anchor)
        anchor_name = args.anchor.name
    elif args.anchor_phrase:
        anchor = prints[args.anchor_phrase]
        anchor_name = args.anchor_phrase
    else:
        # The medoid: the clip closest to all the others.
        totals = {k: sum(distance(v, w) for w in prints.values()) for k, v in prints.items()}
        anchor_name = min(totals, key=lambda k: totals[k])
        anchor = prints[anchor_name]

    dists = {k: distance(v, anchor) for k, v in prints.items()}
    values = np.array(list(dists.values()))
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median))) or 1e-6
    outliers = sorted(
        (k for k, d in dists.items() if (d - median) / mad > args.threshold),
        key=lambda k: -dists[k],
    )
    targets = list(dict.fromkeys(outliers + args.also))
    print(f"{args.pack}: anchor {anchor_name}, median distance {median:.2f}")
    for k in targets:
        print(f"  {'outlier' if k in outliers else 'retake '} {k:24} {dists[k]:.2f}")
    if not args.fix or not targets:
        return 0

    preset = presets.load(args.pack)
    voice = FISH_VOICES.get(args.pack, preset.voice)
    provider = providers.get("fish").from_env()
    weights = {p.id: p.weight for p in phrases.load()}
    scratch = synth.parent / "takes"
    scratch.mkdir(exist_ok=True)
    for phrase_id in targets:
        text = preset.lines[phrase_id]
        options = preset.options_for(phrase_id, weights.get(phrase_id, 1.0))
        best, best_d = clips[phrase_id], dists[phrase_id]
        for n in range(args.takes):
            take = scratch / f"{phrase_id}.{n}.mp3"
            provider.synthesize(text, voice, take, options)
            d = distance(fingerprint(take), anchor)
            if d < best_d:
                best, best_d = take, d
        if best != clips[phrase_id]:
            shutil.copyfile(best, clips[phrase_id])
        print(f"  kept {phrase_id:24} {dists[phrase_id]:.2f} -> {best_d:.2f}")
    shutil.rmtree(scratch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
