"""Keep the character off the prompts Waze repeats.

A pack holds one recording per prompt and Waze plays that same file every
time; the nine greetings are the only prompts it rotates. One turn is heard as
a distance callout (often two), then the maneuver, and Waze replays the
maneuver clip at each distance. A catchphrase on any of those is heard two or
three times per junction, every junction, which is what made "if you please"
unbearable on a real drive.

So those prompts are plain wording in the character's voice, and the writing
goes where repetition does not bite: greetings, arrival, reroute, alerts, the
U-turn, the far roundabout exits and the long-range callouts (one mile, one
and one and a half kilometres), which are heard rarely and mostly on highways.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PRESETS = Path(__file__).resolve().parent.parent / "presets"

# Punctuation may differ ("!" changes delivery, not words); the words may not.
PLAIN = {
    "in_tenth_mile": "in point one miles",
    "in_quarter_mile": "in a quarter of a mile",
    "in_half_mile": "in half a mile",
    "in_200_meters": "in two hundred meters",
    "in_400_meters": "in four hundred meters",
    "in_800_meters": "in eight hundred meters",
    "turn_left": "turn left",
    "turn_right": "turn right",
    "keep_left": "keep left",
    "keep_right": "keep right",
    "exit_left": "take the exit on the left",
    "exit_right": "take the exit on the right",
    "go_straight": "straight ahead",
    "and_then": "and then",
    "roundabout": "at the roundabout",
}

# Every greeting opening "Eh, what's up, doc?" was an explicit product call.
GREETING_EXEMPT = {"bugs-bunny"}
MAX_SHARED_OPENING = 3


def words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", text.lower()).split())


def presets() -> list[tuple[str, dict[str, str]]]:
    return [
        (path.stem, json.loads(path.read_text(encoding="utf-8"))["lines"])
        for path in sorted(PRESETS.glob("*.json"))
    ]


class RepeatedPromptTests(unittest.TestCase):
    def test_repeated_prompts_are_plain(self) -> None:
        for name, lines in presets():
            for phrase_id, plain in PLAIN.items():
                with self.subTest(preset=name, prompt=phrase_id):
                    self.assertEqual(
                        words(lines[phrase_id]),
                        plain,
                        f"{name}.{phrase_id} is heard at every junction; keep it plain",
                    )

    def test_greetings_do_not_share_an_opening(self) -> None:
        """Waze picks a greeting at random. The same catchphrase opening most of
        them still means hearing it most drives."""
        for name, lines in presets():
            if name in GREETING_EXEMPT:
                continue
            openings: dict[str, int] = {}
            for i in range(1, 10):
                opening = " ".join(words(lines[f"start_drive_{i}"]).split()[:3])
                openings[opening] = openings.get(opening, 0) + 1
            with self.subTest(preset=name):
                worst = max(openings, key=lambda k: openings[k])
                self.assertLessEqual(
                    openings[worst],
                    MAX_SHARED_OPENING,
                    f"{name}: {openings[worst]} of 9 greetings open with '{worst}'",
                )


if __name__ == "__main__":
    unittest.main()
