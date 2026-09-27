"""Runway calls for THE GETAWAY, each one logged to film/runway3/ledger.json.

The key is read from the RUNWAY_KEY environment variable only and is never
written anywhere. Every call (kept or not) is appended to the ledger with the
balance observed before and after. Paths are relative to film/runway3/.

    python scripts/runway_getaway.py balance
    python scripts/runway_getaway.py image stills/KF_walk_a.png --prompt-file prompts/KF_walk.txt \
        --model gen4_image --ref car=refs/car.jpg --purpose "cold open keyframe"
    python scripts/runway_getaway.py video takes/V01_a.mp4 --first stills/KF_walk_a.png \
        [--last stills/KF_x.png] --seconds 8 --prompt-file prompts/V01.txt --purpose "..."
    python scripts/runway_getaway.py sfx sfx/rain_roof.mp3 --seconds 8 --prompt "..."
    python scripts/runway_getaway.py verdict takes/V01_a.mp4 "kept: src 1.2 to 3.2"

Gemini images come back at 2752x1536; a 1920x1080 copy (scaled, centre-cropped)
is written next to them as <name>_1080.png, which is what the video calls use.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "film" / "runway3"
LEDGER = ROOT / "ledger.json"
API = "https://api.dev.runwayml.com"
NEGATIVE = (
    "talking, lip sync, mouthing words, phone held to ear, phone call, text, subtitles, captions, "
    "logos, watermark, readable signs, license plate text, extra fingers, deformed hands, face morphing, "  # noqa: E501
    "identity change, extra people, cartoon, shaky handheld camera"
)
IMAGE_COST = {"gen4_image": 8, "gen4_image_turbo": 2, "gemini_image3_pro": 20}


def call(method: str, path: str, body: dict | None = None) -> dict:
    key = os.environ["RUNWAY_KEY"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(6 * (attempt + 1))
                continue
            raise SystemExit(f"HTTP {e.code} on {path}: {msg}") from e
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == 5:
                raise
            time.sleep(6 * (attempt + 1))
    raise SystemExit("unreachable")


def balance() -> int:
    return int(call("GET", "/v1/organization")["creditBalance"])


def data_uri(path: Path) -> str:
    """JPEG data URI (keeps big stills under the 5 MB limit)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-q:v", "2", "-f", "image2", "-c:v", "mjpeg", "-"],  # noqa: E501
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def download(task_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        url = call("GET", f"/v1/tasks/{task_id}")["output"][0]
        tmp = dest.with_suffix(dest.suffix + ".part")
        r = subprocess.run(
            ["curl", "-sS", "-L", "--retry", "6", "--retry-all-errors", "--retry-delay", "3",
             "-o", str(tmp), url],
        )  # fmt: skip
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 10000:
            if dest.suffix.lower() == ".png":
                # whatever came back (png/jpg/webp), store a real PNG
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-i", str(tmp), str(dest)], check=True
                )
                tmp.unlink()
            else:
                tmp.replace(dest)
            return
        time.sleep(6)
    raise SystemExit(f"download failed for {task_id}")


def log(entry: dict) -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"calls": []}
    ledger["calls"].append(entry)
    ledger["total_credits"] = sum(c.get("credits") or 0 for c in ledger["calls"])
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def wait(task_id: str) -> dict:
    while True:
        t = call("GET", f"/v1/tasks/{task_id}")
        if t["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return t
        time.sleep(6)


def to_1080(src: Path) -> Path:
    dest = src.with_name(src.stem + "_1080.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf",
         "scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,crop=1920:1080", str(dest)],  # noqa: E501
        check=True,
    )  # fmt: skip
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["image", "video", "sfx", "balance", "verdict"])
    ap.add_argument("out", nargs="?")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--first")
    ap.add_argument("--last")
    ap.add_argument("--ref", action="append", default=[], help="tag=path[:human]")
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--purpose", default="")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--seconds", type=float, default=8)
    ap.add_argument("--model")
    ap.add_argument("--ratio")
    a = ap.parse_args()

    if a.kind == "balance":
        print(balance())
        return 0
    if a.kind == "verdict":
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        hits = [c for c in ledger["calls"] if c.get("output") == a.out]
        if not hits:
            raise SystemExit(f"no ledger entry with output {a.out}")
        hits[-1]["verdict"] = a.text
        LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0

    prompt = (
        (ROOT / a.prompt_file).read_text(encoding="utf-8").strip() if a.prompt_file else a.prompt
    )
    before = balance()
    refs = []
    if a.kind == "video":
        model = a.model or "veo3.1_fast"
        ratio = a.ratio or "1920:1080"
        if a.last:
            image = [
                {"uri": data_uri(ROOT / a.first), "position": "first"},
                {"uri": data_uri(ROOT / a.last), "position": "last"},
            ]
        else:
            image = data_uri(ROOT / a.first)
        body = {
            "model": model,
            "promptImage": image,
            "promptText": prompt,
            "ratio": ratio,
            "duration": int(a.seconds),
        }
        if model.startswith("veo"):
            body["audio"] = False
            body["negativePrompt"] = NEGATIVE
        endpoint = "/v1/image_to_video"
        expected = int(a.seconds) * {"veo3.1_fast": 10, "veo3.1": 20, "gen4_turbo": 5}.get(
            model, 10
        )
    elif a.kind == "image":
        model = a.model or "gen4_image"
        ratio = a.ratio or ("2752:1536" if model.startswith("gemini") else "1920:1080")
        for spec in a.ref:
            tag, path = spec.split("=", 1)
            human = path.endswith(":human")
            path = path.removesuffix(":human")
            r = {"uri": data_uri(ROOT / path), "tag": tag}
            if model.startswith("gemini"):
                r["subject"] = "human" if human else "object"
            refs.append(r)
            refs[-1]["_path"] = path
        body = {"model": model, "promptText": prompt, "ratio": ratio}
        if refs:
            body["referenceImages"] = [{k: v for k, v in r.items() if k != "_path"} for r in refs]
        endpoint = "/v1/text_to_image"
        expected = IMAGE_COST.get(model, 20)
    else:
        model = "eleven_text_to_sound_v2"
        ratio = None
        body = {"model": model, "promptText": prompt, "duration": a.seconds}
        endpoint = "/v1/sound_effect"
        expected = int(round(a.seconds))
    if a.seed is not None:
        body["seed"] = a.seed
    if expected > before:
        raise SystemExit(f"not enough credits: {before} < {expected}")
    task = call("POST", endpoint, body)
    task_id = task["id"]
    print(f"task {task_id} submitted ({a.out}), balance before {before}", flush=True)
    t = wait(task_id)
    after = balance()
    entry = {
        "time": dt.datetime.now().isoformat(timespec="seconds"),
        "task_id": task_id,
        "endpoint": endpoint,
        "model": model,
        "ratio": ratio,
        "seconds": a.seconds if a.kind != "image" else None,
        "credits_expected": expected,
        # The published price; failed tasks are not charged. Calls can overlap
        # (two image jobs at once), so the observed balance delta is kept apart.
        "credits": expected if t["status"] == "SUCCEEDED" else 0,
        "balance_delta_observed": before - after,
        "balance_before": before,
        "balance_after": after,
        "purpose": a.purpose,
        "first": a.first,
        "last": a.last,
        "refs": [f"{r['tag']}={r['_path']}" for r in refs] or None,
        "prompt": prompt,
        "seed": a.seed,
        "status": t["status"],
        "output": a.out if t["status"] == "SUCCEEDED" else None,
        "verdict": "pending review",
    }
    if t["status"] == "SUCCEEDED":
        download(task_id, ROOT / a.out)
        if a.kind == "image" and model.startswith("gemini"):
            to_1080(ROOT / a.out)
    else:
        entry["failure"] = t.get("failure") or t.get("failureCode")
    log(entry)
    print(
        f"{t['status']} {task_id} -> {a.out}; credits {before - after}; balance {after}"
        + (f"; failure {entry.get('failure')}" if t["status"] != "SUCCEEDED" else ""),
        flush=True,
    )
    return 0 if t["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
