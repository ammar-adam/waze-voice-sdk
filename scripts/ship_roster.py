"""Take the roster from scripts and voices to checked, staged, published packs.

    python scripts/ship_roster.py status
    python scripts/ship_roster.py build [--shard k/n] [--only slug]   # needs $FISH_API_KEY
    python scripts/ship_roster.py stage                               # into the uploader
    python scripts/ship_roster.py publish upload.log                  # UUIDs -> the site

A character is ready to build when it has a preset (presets/<slug>.json), a
voice pick (roster/voices.json, from find_voices.py) and a blurb
(roster/blurbs/*.json). `build` does, per character:

1. writes the picked model id into the preset,
2. generates all 43 clips and exports the pack (wvs quickstart),
3. evens out the voice (voice_consistency --fix),
4. transcribes every clip and retakes any that do not say their line,
5. re-exports, and records the result in roster/built/<slug>.json.

A pack with more than MAX_UNCLEAR lines still unclear after retakes is marked
"review" and is not staged: that is a voice that cannot say the script.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from stage_for_upload import DEFAULT_UPLOADER, stage  # noqa: E402

from waze_voice import packs, phrases, presets, providers  # noqa: E402

ROSTER = REPO / "roster"
BUILT = ROSTER / "built"
CLEAR = 0.85
TAKES = 3
MAX_UNCLEAR = 5
# Packs that babble on purpose. A transcript of gibberish never matches its
# script, so for these only the words a driver needs ("left", "half a mile",
# "police") have to be heard, and lines with none are not checked.
GIBBERISH = {"king-bob"}
SPOKEN = {"0.1": "point one", "1.5": "one point five", "u turn": "you turn", "uturn": "you turn"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def roster() -> list[dict]:
    """Main-roster characters, each with its voice pick, blurb and colours where known."""
    picks = (
        load_json(ROSTER / "voices.json")["voices"] if (ROSTER / "voices.json").is_file() else {}
    )
    extra: dict[str, dict] = {}
    for folder in ("blurbs", "colors"):
        for path in sorted((ROSTER / folder).glob("*.json")):
            for slug, value in load_json(path).items():
                extra.setdefault(slug, {}).update(value)
    out = []
    for entry in load_json(ROSTER / "roster.json")["main"]:
        slug = entry["slug"]
        out.append({**entry, **extra.get(slug, {}), "pick": picks.get(slug, {})})
    return out


def state(entry: dict) -> str:
    slug = entry["slug"]
    built = BUILT / f"{slug}.json"
    if built.is_file():
        return load_json(built)["status"]
    if not (REPO / "presets" / f"{slug}.json").is_file():
        return "no-preset"
    if entry["pick"].get("status") != "ok":
        return "no-voice"
    return "ready"


ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
]


def _number(match: re.Match) -> str:
    """A transcriber writes "200" where the script says "two hundred"."""
    n = int(match.group())
    if n < len(ONES):
        return ONES[n]
    if n % 1000 == 0 and n // 1000 < len(ONES):
        return f"{ONES[n // 1000]} thousand"
    if n % 100 == 0 and n // 100 < len(ONES):
        return f"{ONES[n // 100]} hundred"
    return match.group()


def norm(text: str) -> str:
    text = text.lower().replace("-", " ")
    for written, spoken in SPOKEN.items():
        text = text.replace(written, spoken)
    text = re.sub(r"\d+", _number, text.replace(",", ""))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text).split())


_whisper = None


def heard(path: Path) -> str:
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel

        _whisper = WhisperModel("small.en", device="cpu", compute_type="int8")
    segments, _ = _whisper.transcribe(str(path), language="en", beam_size=5)
    return " ".join(s.text for s in segments).strip()


def clarity(line: str, path: Path) -> tuple[float, str]:
    text = heard(path)
    return difflib.SequenceMatcher(None, norm(line), norm(text)).ratio(), text


def navigation_clarity(phrase_id: str, path: Path) -> tuple[float, str] | None:
    """1.0 when every required token is heard, 0.0 when one is not; None if none."""
    required = presets.REQUIRED_TOKENS.get(phrase_id)
    if not required:
        return None
    text = heard(path)
    ok = all(any(presets.contains_word(text, t) for t in options) for options in required)
    return (1.0 if ok else 0.0), text


def score(slug: str, phrase_id: str, line: str, path: Path) -> tuple[float, str] | None:
    if slug in GIBBERISH:
        return navigation_clarity(phrase_id, path)
    return clarity(line, path)


def run(*args: str) -> int:
    return subprocess.run([sys.executable, *args], cwd=str(REPO)).returncode


def quickstart(slug: str, *, force: bool) -> int:
    command = ["scripts/wvs.py", "quickstart", "--pack", slug, "--preset", slug]
    return run(*command, "--accept-voice-terms", *(["--force"] if force else []))


def build_one(entry: dict) -> dict:
    slug = entry["slug"]
    preset_path = REPO / "presets" / f"{slug}.json"
    doc = load_json(preset_path)
    if doc.get("provider") == "fish" and doc.get("voice") != entry["pick"]["model_id"]:
        doc["voice"] = entry["pick"]["model_id"]
        preset_path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if not packs.exists(slug):
        packs.create(slug, label=entry.get("waze_name") or entry["name"])
    synth = REPO / "packs" / slug / "audio" / "synthesized"
    fresh = len(list(synth.glob("*.mp3"))) < 43
    if quickstart(slug, force=fresh):
        return {"status": "failed", "reason": "quickstart failed"}
    run("scripts/voice_consistency.py", slug, "--fix", "--takes", "3")

    preset = presets.load(slug)
    provider = providers.get(preset.provider).from_env()
    weights = {p.id: p.weight for p in phrases.load()}
    scratch = synth.parent / "retakes"
    scratch.mkdir(exist_ok=True)
    unclear, retaken = {}, 0
    for clip in sorted(synth.glob("*.mp3")):
        line = preset.lines.get(clip.stem)
        if not line:
            continue
        first = score(slug, clip.stem, line, clip)
        if first is None or first[0] >= CLEAR:
            continue
        best = (*first, None)
        for n in range(TAKES):
            take = scratch / f"{clip.stem}.{n}.mp3"
            options = preset.options_for(clip.stem, weights.get(clip.stem, 1.0))
            provider.synthesize(line, preset.voice, take, options)
            took, text = score(slug, clip.stem, line, take)
            if took > best[0]:
                best = (took, text, take)
            if took >= CLEAR:
                break
        if best[2] is not None:
            shutil.copyfile(best[2], clip)
            retaken += 1
        if best[0] < CLEAR:
            unclear[clip.stem] = {"line": line, "heard": best[1], "clarity": round(best[0], 2)}
    shutil.rmtree(scratch, ignore_errors=True)
    if quickstart(slug, force=False):
        return {"status": "failed", "reason": "re-export failed"}
    status = "built" if len(unclear) <= MAX_UNCLEAR else "review"
    return {"status": status, "retaken": retaken, "unclear": unclear, "voice": preset.voice}


def cmd_build(args: argparse.Namespace) -> int:
    BUILT.mkdir(exist_ok=True)
    k, n = (int(x) for x in args.shard.split("/"))
    for i, entry in enumerate(roster()):
        slug = entry["slug"]
        if i % n != k or (args.only and slug not in args.only):
            continue
        current = state(entry)
        if current != "ready" and not (args.only and current in ("failed", "review", "built")):
            continue
        print(f"\n=== {entry['name']} ===", flush=True)
        try:
            result = build_one(entry)
        except Exception as error:  # noqa: BLE001 - one bad pack must not stop the run
            result = {"status": "failed", "reason": str(error)[:300]}
        (BUILT / f"{slug}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"=== {slug}: {result['status']} ===", flush=True)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    groups: dict[str, list[str]] = {}
    for entry in roster():
        groups.setdefault(state(entry), []).append(entry["slug"])
    for name, slugs in sorted(groups.items()):
        print(f"{name:10} {len(slugs):3}  {' '.join(slugs)}")
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    staged = 0
    for entry in roster():
        if state(entry) != "built" or (args.only and entry["slug"] not in args.only):
            continue
        pack_dir = REPO / "packs" / entry["slug"] / "audio" / "export" / "pack"
        name = entry.get("waze_name") or entry["name"]
        if stage(pack_dir, args.uploader, name, entry["slug"]) == 0:
            staged += 1
    print(f"staged {staged}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """Read the uploader's output for name -> UUID, then update the site's data."""
    log = Path(args.log).read_text(encoding="utf-8", errors="replace")
    found = dict(
        re.findall(
            r"Upload of (.+?) successful\.\s+https://waze\.com/ul\?acvp=([0-9a-f-]{36})", log
        )
    )
    voices_path = REPO / "site" / "voices.json"
    site = load_json(voices_path)
    live = {v["slug"]: v for v in site["voices"]}
    css_path = REPO / "site" / "characters.css"
    css = css_path.read_text(encoding="utf-8")
    added = []
    for entry in roster():
        slug, name = entry["slug"], entry.get("waze_name") or entry["name"]
        if name not in found or state(entry) != "built":
            continue
        if not (REPO / "site" / "faces" / f"{slug}.svg").is_file() or "bg" not in entry:
            print(f"skipped {slug}: no face or colours yet")
            continue
        record = {
            "slug": slug,
            "preset": slug,
            "name": entry["name"],
            "waze_name": name,
            "blurb": entry.get("blurb", ""),
            "uuid": found[name],
            "rights": presets.load(slug).rights.status,
            "category": entry["category"],
            "tags": entry.get("tags", []),
        }
        if slug in live:
            live[slug].update(record)
        else:
            site["voices"].append(record)
            added.append(slug)
        if f"#{slug} " not in css and f"#{slug}{{" not in css:
            css += (
                f"#{slug} {{ --bg: {entry['bg']}; --tone: {entry['tone']}; "
                f"--tone-ink: {entry['tone_ink']}; }}\n"
            )
    voices_path.write_text(json.dumps(site, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    css_path.write_text(css, encoding="utf-8")
    print(f"{len(found)} uploads read, {len(added)} voices added: {' '.join(added)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(run=cmd_status)
    build = sub.add_parser("build")
    build.add_argument("--shard", default="0/1")
    build.add_argument("--only", action="append")
    build.set_defaults(run=cmd_build)
    stage_cmd = sub.add_parser("stage")
    stage_cmd.add_argument("--only", action="append")
    stage_cmd.add_argument("--uploader", type=Path, default=DEFAULT_UPLOADER)
    stage_cmd.set_defaults(run=cmd_stage)
    publish = sub.add_parser("publish")
    publish.add_argument("log")
    publish.set_defaults(run=cmd_publish)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
