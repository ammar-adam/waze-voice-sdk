"""Generate one Tough Crowd take with the Runway API and log it to the ledger.

The key is read from the RUNWAY_KEY environment variable only; it is never
written anywhere. Every call (kept or not) is appended to
film/runway2/ledger.json with the balance observed before and after.

    RUNWAY_KEY=... python scripts/runway_gen.py video S06 takes/S06_a.mp4 \
        --keyframe keyframes/KF06b_driver_cu_traffic.png --prompt-file p.txt
    RUNWAY_KEY=... python scripts/runway_gen.py sfx cab_idle sfx/cab_idle.mp3 \
        --prompt "..." --seconds 8
    RUNWAY_KEY=... python scripts/runway_gen.py balance

Paths are relative to film/runway2/.
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

ROOT = Path(__file__).resolve().parent.parent / "film" / "runway2"
LEDGER = ROOT / "ledger.json"
API = "https://api.dev.runwayml.com"
NEGATIVE = (
    "talking, lip sync, mouthing words, phone held to ear, phone call, text, subtitles, captions, "
    "logos, watermark, readable signs, license plate text, extra fingers, deformed hands, face morphing, "
    "identity change, camera shake, cartoon"
)


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
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(5 * (attempt + 1))
                continue
            raise SystemExit(f"HTTP {e.code} on {path}: {msg}")
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))
    raise SystemExit("unreachable")


def balance() -> int:
    return int(call("GET", "/v1/organization")["creditBalance"])


def download(task_id: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        url = call("GET", f"/v1/tasks/{task_id}")["output"][0]
        r = subprocess.run(
            ["curl", "-sS", "-L", "--retry", "5", "--retry-all-errors", "--retry-delay", "3",
             "-o", str(dest), url],
        )  # fmt: skip
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 10000:
            return
        time.sleep(5)
    raise SystemExit(f"download failed for {task_id}")


def log(entry: dict) -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["calls"].append(entry)
    ledger["total_credits"] = sum(c.get("credits") or 0 for c in ledger["calls"])
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def wait(task_id: str) -> dict:
    while True:
        t = call("GET", f"/v1/tasks/{task_id}")
        if t["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return t
        time.sleep(8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["video", "sfx", "balance"])
    ap.add_argument("shot", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--keyframe")
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--purpose", default="")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--seconds", type=float, default=8)
    ap.add_argument("--model", default="veo3.1_fast")
    ap.add_argument("--ratio", default="1920:1080")
    a = ap.parse_args()

    if a.kind == "balance":
        print(balance())
        return 0

    prompt = Path(a.prompt_file).read_text(encoding="utf-8").strip() if a.prompt_file else a.prompt
    before = balance()
    if a.kind == "video":
        img = (ROOT / a.keyframe).read_bytes()
        body = {
            "model": a.model,
            "promptImage": "data:image/png;base64," + base64.b64encode(img).decode(),
            "promptText": prompt,
            "ratio": a.ratio,
            "duration": int(a.seconds),
        }
        if a.model.startswith("veo"):
            body["audio"] = False
            body["negativePrompt"] = NEGATIVE
        if a.seed is not None:
            body["seed"] = a.seed
        endpoint = "/v1/image_to_video"
        expected = int(a.seconds) * (10 if a.model.startswith("veo3.1_fast") else 5)
    else:
        a.model = "eleven_text_to_sound_v2"
        body = {"model": a.model, "promptText": prompt, "duration": a.seconds}
        endpoint = "/v1/sound_effect"
        expected = int(round(a.seconds))
    if expected > before:
        raise SystemExit(f"not enough credits: {before} < {expected}")
    task = call("POST", endpoint, body)
    task_id = task["id"]
    print(f"task {task_id} submitted ({a.shot}), balance before {before}", flush=True)
    t = wait(task_id)
    after = balance()
    entry = {
        "time": dt.datetime.now().isoformat(timespec="seconds"),
        "task_id": task_id,
        "endpoint": endpoint,
        "model": a.model,
        "ratio": a.ratio if a.kind == "video" else None,
        "seconds": a.seconds,
        "credits_expected": expected,
        "credits": before - after,
        "balance_before": before,
        "balance_after": after,
        "shot": a.shot,
        "purpose": a.purpose,
        "keyframe": a.keyframe,
        "seed": a.seed,
        "status": t["status"],
        "output": a.out if t["status"] == "SUCCEEDED" else None,
        "verdict": "pending review",
    }
    if t["status"] == "SUCCEEDED":
        download(task_id, ROOT / a.out)
    else:
        entry["failure"] = t.get("failure") or t.get("failureCode")
    log(entry)
    print(f"{t['status']} {task_id} -> {a.out}; credits {before - after}; balance {after}", flush=True)
    return 0 if t["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
