"""Find and audition a Fish Audio voice model for every character in the roster.

    python scripts/find_voices.py                 # every character without a pick
    python scripts/find_voices.py --only yoda     # one (repeatable)
    python scripts/find_voices.py --redo yoda     # forget a pick and try again

For each character: search Fish by name, keep English models whose title is
about that character, audition the best few on two navigation lines, transcribe
them, and keep the clearest. Everything is cached under voice-auditions/find/
(git-ignored), so a rerun costs nothing for work already done. Results go to
roster/voices.json; a human still needs to judge the low-confidence ones by ear.

Needs $FISH_API_KEY, faster-whisper and librosa.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from waze_voice import providers  # noqa: E402

ROSTER = REPO / "roster" / "roster.json"
OUT = REPO / "roster" / "voices.json"
CACHE = REPO / "voice-auditions" / "find"
LINES = [
    "In a quarter of a mile, turn left.",
    "Police ahead! You have arrived at your destination.",
]
OPTIONS = {"temperature": 0.5, "top_p": 0.6}
MAX_AUDITIONS = 3

# Extra search terms where the plain name finds too little.
QUERIES: dict[str, list[str]] = {
    "spider-man": ["Spider-Man", "Spiderman", "Peter Parker"],
    "c-3po": ["C-3PO", "C3PO", "Threepio"],
    "obi-wan-kenobi": ["Obi-Wan Kenobi", "Obi Wan", "Kenobi"],
    "emperor-palpatine": ["Palpatine", "Emperor Palpatine", "Darth Sidious"],
    "stormtrooper": ["Stormtrooper", "Clone Trooper"],
    "iron-man": ["Iron Man", "Tony Stark"],
    "joker": ["Joker", "The Joker"],
    "jack-sparrow": ["Jack Sparrow", "Captain Jack Sparrow"],
    "scooby-doo": ["Scooby-Doo", "Scooby Doo", "Scooby"],
    "homer-simpson": ["Homer Simpson", "Homer"],
    "bart-simpson": ["Bart Simpson", "Bart"],
    "mr-burns": ["Mr. Burns", "Mr Burns", "Montgomery Burns"],
    "stewie-griffin": ["Stewie Griffin", "Stewie"],
    "rick-sanchez": ["Rick Sanchez", "Rick and Morty Rick"],
    "morty": ["Morty Smith", "Morty"],
    "butters": ["Butters", "Butters Stotch"],
    "mr-mackey": ["Mr. Mackey", "Mr Mackey", "Mackey"],
    "archer": ["Sterling Archer", "Archer"],
    "spongebob": ["SpongeBob", "Spongebob Squarepants"],
    "patrick-star": ["Patrick Star", "Patrick"],
    "mr-krabs": ["Mr. Krabs", "Mr Krabs", "Krabs"],
    "po": ["Po Kung Fu Panda", "Kung Fu Panda"],
    "geralt": ["Geralt", "Geralt of Rivia"],
    "solid-snake": ["Solid Snake", "Snake Metal Gear"],
    "hal-9000": ["HAL 9000", "HAL9000"],
    "jarvis": ["JARVIS", "Jarvis"],
    "doc-brown": ["Doc Brown", "Emmett Brown"],
    "dumbledore": ["Dumbledore", "Albus Dumbledore"],
    "snape": ["Snape", "Severus Snape"],
    "master-chief": ["Master Chief", "Halo Master Chief"],
    "optimus-prime": ["Optimus Prime", "Optimus"],
    "lightning-mcqueen": ["Lightning McQueen", "McQueen"],
    "buzz-lightyear": ["Buzz Lightyear", "Buzz"],
    "marvin-the-martian": ["Marvin the Martian", "Marvin Martian"],
    "ted": ["Ted bear", "Ted Seth MacFarlane", "Ted"],
}
BAD = re.compile(
    r"\b(cover|sings?|song|rap|español|espanol|latino|portugu|deutsch|fran[cç]ais|"
    r"italiano|русск|日本|中文|한국|arab|hindi|turk|polsk|castellano|dublado|ptbr|pt-br)\b",
    re.I,
)


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower().replace("-", " ")).split())


def fish(path: str) -> dict:
    request = urllib.request.Request(
        "https://api.fish.audio" + path,
        headers={"Authorization": "Bearer " + os.environ["FISH_API_KEY"]},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def search(slug: str, name: str) -> list[dict]:
    cached = CACHE / slug / "search.json"
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    found: dict[str, dict] = {}
    for query in QUERIES.get(slug, [name]):
        for sort in ("score", "task_count"):
            q = urllib.parse.urlencode({"title": query, "page_size": 20, "sort_by": sort})
            for item in fish("/model?" + q).get("items", []):
                found.setdefault(item["_id"], item)
    keep = [
        {
            "id": m["_id"],
            "title": m.get("title") or "",
            "description": (m.get("description") or "")[:300],
            "likes": m.get("like_count") or 0,
            "tasks": m.get("task_count") or 0,
            "languages": m.get("languages") or [],
        }
        for m in found.values()
    ]
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(keep, indent=1, ensure_ascii=False), encoding="utf-8")
    return keep


def rank(slug: str, name: str, models: list[dict]) -> list[dict]:
    """Models whose title is about this character, most used first."""
    wanted = [norm(q) for q in QUERIES.get(slug, [name])] + [norm(name)]
    ranked = []
    for m in models:
        title = norm(m["title"])
        if not title or BAD.search(m["title"]) or BAD.search(m["description"]):
            continue
        if m["languages"] and "en" not in m["languages"]:
            continue
        # The title has to name the character outright. A near miss ("Maki" for
        # "Maui") is a different voice, however clear it sounds.
        padded = f" {title} "
        if not any(f" {w} " in padded for w in wanted):
            continue
        match = 1.0
        # Exact-name titles first, then by how much the model is actually used.
        exact = 1 if any(title == w for w in wanted) else 0
        m = {**m, "match": round(match, 2)}
        ranked.append((match >= 1.0, exact, m["tasks"] + 40 * m["likes"], m))
    ranked.sort(key=lambda r: r[:3], reverse=True)
    return [r[3] for r in ranked]


_whisper = None


def transcribe(path: Path) -> str:
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel

        _whisper = WhisperModel("small.en", device="cpu", compute_type="int8")
    segments, _ = _whisper.transcribe(str(path), language="en", beam_size=5)
    return " ".join(s.text for s in segments).strip()


def pitch_of(path: Path) -> float:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(path), sr=16000, mono=True)
    f0 = librosa.yin(y, fmin=50, fmax=600, sr=sr)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    n = min(len(f0), len(rms))
    voiced = f0[:n][rms[:n] > 0.3 * rms.max()]
    return float(np.median(voiced)) if len(voiced) else 0.0


def audition(slug: str, model: dict, provider) -> dict:
    folder = CACHE / slug / model["id"]
    result_file = folder / "result.json"
    if result_file.is_file():
        return json.loads(result_file.read_text(encoding="utf-8"))
    folder.mkdir(parents=True, exist_ok=True)
    clarity, heard, seconds, pitches = [], [], [], []
    import librosa

    for i, line in enumerate(LINES):
        clip = folder / f"{i}.mp3"
        try:
            provider.synthesize(line, model["id"], clip, OPTIONS)
        except Exception as error:  # noqa: BLE001 - a withdrawn model is a normal outcome
            result = {"error": str(error)[:200]}
            result_file.write_text(json.dumps(result), encoding="utf-8")
            return result
        text = transcribe(clip)
        heard.append(text)
        clarity.append(round(difflib.SequenceMatcher(None, norm(line), norm(text)).ratio(), 2))
        seconds.append(round(librosa.get_duration(path=str(clip)), 2))
        pitches.append(pitch_of(clip))
    result = {
        "clarity": clarity,
        "heard": heard,
        "seconds": seconds,
        "pitch_hz": round(sum(pitches) / len(pitches)),
    }
    result_file.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def usable(result: dict) -> bool:
    if "error" in result:
        return False
    sane = all(0.8 <= s <= 9 for s in result["seconds"])
    return min(result["clarity"]) >= 0.9 and sane


def popular(model: dict) -> bool:
    return model["likes"] >= 10 or model["tasks"] >= 2000


def choose(slug: str, name: str, provider) -> dict:
    ranked = rank(slug, name, search(slug, name))
    tried = []
    for model in ranked[:MAX_AUDITIONS]:
        result = audition(slug, model, provider)
        tried.append({**model, **result})
        print(f"  {model['title'][:34]:34} likes {model['likes']:>4} {result}", flush=True)
    # Only models people actually use: a pick has to be clear AND popular.
    good = [t for t in tried if usable(t) and popular(t)]
    if not good:
        if not ranked:
            why = "no model on Fish with this character's name"
        elif not any(popular(t) for t in tried):
            why = "no well-used model (needs 10+ likes or 2,000+ uses)"
        else:
            why = "no clear take from a well-used model"
        return {"name": name, "status": "none", "reason": why, "tried": tried}
    best = max(good, key=lambda t: t["tasks"] + 40 * t["likes"])
    confidence = "high" if best["likes"] >= 20 or best["tasks"] >= 5000 else "medium"
    return {
        "name": name,
        "status": "ok",
        "model_id": best["id"],
        "title": best["title"],
        "likes": best["likes"],
        "tasks": best["tasks"],
        "description": best["description"],
        "clarity": best["clarity"],
        "pitch_hz": best["pitch_hz"],
        "confidence": confidence,
        "runners_up": [
            {k: t.get(k) for k in ("id", "title", "likes", "clarity", "pitch_hz", "description")}
            for t in tried
            if t["id"] != best["id"]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append")
    parser.add_argument("--redo", action="append", default=[])
    parser.add_argument("--alternates", action="store_true", help="Run the alternates list too.")
    parser.add_argument("--shard", default="0/1", help="k/n: take every nth character, from k.")
    args = parser.parse_args(argv)

    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    entries = roster["main"] + (roster["alternates"] if args.alternates else [])
    k, n = (int(x) for x in args.shard.split("/"))
    provider = providers.get("fish").from_env()
    # One pick file per character, so shards running side by side never collide.
    for i, entry in enumerate(entries):
        slug = entry["slug"]
        pick_file = CACHE / slug / "pick.json"
        if i % n != k or (args.only and slug not in args.only):
            continue
        if pick_file.is_file() and slug not in args.redo:
            continue
        print(f"{entry['name']}", flush=True)
        pick = {**choose(slug, entry["name"], provider), "category": entry["category"]}
        pick_file.parent.mkdir(parents=True, exist_ok=True)
        pick_file.write_text(json.dumps(pick, indent=1, ensure_ascii=False), encoding="utf-8")

    voices = {}
    for entry in roster["main"] + roster["alternates"]:
        pick_file = CACHE / entry["slug"] / "pick.json"
        if pick_file.is_file():
            voices[entry["slug"]] = json.loads(pick_file.read_text(encoding="utf-8"))
    OUT.write_text(
        json.dumps({"voices": voices}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    counts = {
        key: sum(1 for p in voices.values() if p.get("confidence") == key or p["status"] == key)
        for key in ("high", "medium", "low", "none")
    }
    print(f"\n{len(voices)} picked {counts} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
