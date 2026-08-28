"""Audition voices for each character: invent one, and search for existing ones.

Descriptions here name a vocal archetype, never a character or a performer.
That is not only a rights position, it is the practical one: ElevenLabs bans
voice names containing "names of public individuals or entities", only shares
human-verified professional clones, and moderates requests. Asking it for a
named character gets you nothing. Asking it for "an elderly, soft, husky,
dozy bear" gets you a voice.

    python scripts/audition_characters.py --only pooh
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from waze_voice import console, voicelab  # noqa: E402


class CharacterSpec(TypedDict):
    description: str
    search: list[str]


OUT = Path(__file__).resolve().parent.parent / "voice-auditions"

# description: what to invent.  search: archetypes to look for in the library.
CHARACTERS: dict[str, CharacterSpec] = {
    "pooh": {
        "description": (
            "An elderly bear with a soft, breathy, slightly husky voice, a little "
            "high and round, with a small smile in it. Speaks slowly and "
            "hesitantly, pausing to think mid-sentence as though gently muddled "
            "but entirely well meaning. Warm, dozy, unhurried, never brisk."
        ),
        "search": ["grandpa", "warm elderly storyteller", "gentle old man", "dozy"],
    },
    "tigger": {
        "description": (
            "A boisterous, bouncing character voice: loud, springy and exuberant, "
            "tumbling over its own words with delight. Bright, brash, slightly "
            "slurred, irrepressibly confident and always in motion."
        ),
        "search": ["energetic cartoon", "bouncy excitable", "playful character"],
    },
    "eeyore": {
        "description": (
            "An elderly donkey with a slow, flat, deeply gloomy monotone. "
            "Resigned, mournful and drawling, entirely without hope but never "
            "angry. Long pauses, sagging intonation, quietly certain that it will "
            "not work out."
        ),
        "search": ["gloomy monotone", "depressed deadpan", "melancholy old"],
    },
    "mouse": {
        "description": (
            "A small, cheerful cartoon mouse: very high pitched, bright and "
            "squeaky, boyish and eager, with a light laugh in the voice and an "
            "endless supply of enthusiasm."
        ),
        "search": ["squeaky", "high pitched cartoon", "mouse"],
    },
    "monster": {
        "description": (
            "A large, furry, good-natured monster: deep, gravelly and growling, "
            "greedy and childlike, speaking in blunt excited bursts with simple "
            "delight and no self-control whatsoever."
        ),
        "search": ["monster", "gruff growly creature", "deep cartoon monster"],
    },
    "bear": {
        "description": (
            "A polite young English bear: soft, earnest and well-mannered, gently "
            "hopeful, with a slight formality and an innocent lilt. Sincere, "
            "curious, unfailingly courteous."
        ),
        "search": ["polite young british", "earnest gentle english", "innocent"],
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Just this character.")
    parser.add_argument("--skip-design", action="store_true")
    parser.add_argument("--skip-library", action="store_true")
    args = parser.parse_args(argv)

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("Set ELEVENLABS_API_KEY first. https://elevenlabs.io")
        return 1

    chosen = {args.only: CHARACTERS[args.only]} if args.only else CHARACTERS
    if args.only and args.only not in CHARACTERS:
        print(f"Unknown character. Try: {', '.join(CHARACTERS)}")
        return 1

    for name, spec in chosen.items():
        console.step(name)

        if not args.skip_library:
            seen: set[str] = set()
            for term in spec["search"]:
                try:
                    found = voicelab.search_library(key, search=term, page_size=6)
                except Exception as error:  # noqa: BLE001
                    console.error(f"library search {term!r} failed: {error}")
                    continue
                for voice in found:
                    if voice.voice_id in seen:
                        continue
                    seen.add(voice.voice_id)
                    console.detail(
                        f"[{voice.provenance:11}] {voice.name[:26]:26} "
                        f"{voice.age} {voice.gender} {voice.accent} "
                        f"| {voice.descriptive} | {voice.voice_id}"
                    )
            if not seen:
                console.detail("no library matches")

        if not args.skip_design:
            try:
                previews = voicelab.design(key, spec["description"])
            except Exception as error:  # noqa: BLE001
                console.error(f"voice design failed: {error}")
                continue
            voicelab.write_previews(previews, OUT, f"design-{name}")

    print(f"\nPreviews in {OUT}")
    print("Pick one, then save it as a real voice with voicelab.save_design().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
