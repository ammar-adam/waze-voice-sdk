"""Character presets: a voice, a delivery direction, and 43 rewritten lines.

A preset turns `wvs quickstart --preset eeyore` into a finished pack. It bundles
three things:

- **A voice** from a provider's licensed catalogue, by id.
- **A delivery direction** passed to the provider, which is what carries pace,
  energy, and affect.
- **All 43 Waze prompts rewritten in that character's register.**

The rewrite is the point. A generic navigation line read in a different voice is
a novelty; a line actually written in character is the thing people share.

## Two rules the structure enforces, not the documentation

**1. No cloned performances, ever.** A preset can name a catalogue voice and
describe how to deliver it. It has no field for reference audio, and validation
rejects any attempt to smuggle one through ``provider_options``. Public domain
attaches to a *work*. It never attaches to a later performance of that work, so a
preset that cloned an actor would be unshippable regardless of how old the book
is. Making that structurally impossible is the only way it stays true.

**2. Every line still has to work as navigation.** A driver who has never heard
of the character must know exactly what to do. Validation checks that each line
still contains the thing it is there to communicate: "left" in a left turn,
"quarter mile" in the quarter-mile callout. Distance callouts in particular
cannot get cute with the numbers, and now cannot.

## Where the character actually goes

Not evenly. Maneuver and distance prompts are heard on every single instruction
and carry the most weight in the size budget, so their lines stay tight and the
*delivery direction* does the work. Drive-start greetings, arrival, alerts, and
roundabout ordinals are heard rarely, so they carry the writing.

Spreading flavour evenly across all 43 would blow the size budget and grate on
the driver by the fourth turn. Validation enforces the length side of this.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths
from . import phrases as phrases_module

PRESETS_DIRNAME = "presets"
SCHEMA_VERSION = 1

# Anything that would point the provider at an audio sample. A preset must never
# clone a performance, so these are refused wherever they appear.
CLONING_KEYS = frozenset(
    {
        "speaker_wav",
        "audio_prompt_path",
        "reference",
        "reference_audio",
        "reference_wav",
        "voice_clone",
        "clone",
        "speaker_reference",
        "prompt_audio",
        "voice_sample",
    }
)

RIGHTS_FIELDS = ("source_work", "author", "year", "pd_basis", "covered", "not_covered")

# Frequently-heard prompts stay short: they cost the most budget and are the
# first thing to grate on repetition.
HIGH_FREQUENCY_WEIGHT = 2.0
MAX_CHARS_HIGH_FREQUENCY = 70
MAX_CHARS_OTHER = 160

def normalise(text: str) -> str:
    """Lowercase, and reduce every run of punctuation to a single space.

    Makes matching word-boundary aware without regex: a normalised haystack
    padded with spaces contains " left " only when "left" is a whole word, so
    "leftover" no longer satisfies a left turn.
    """
    out = []
    for char in text.lower():
        out.append(char if char.isalnum() else " ")
    return " ".join("".join(out).split())


def contains_word(haystack: str, phrase: str) -> bool:
    """Whole-word (or whole-phrase) containment on normalised text."""
    return f" {normalise(phrase)} " in f" {normalise(haystack)} "


# Words that would make a direction ambiguous if they turned up in the wrong
# prompt. "Turn left, not right" is a line a driver can act on wrongly.
OPPOSITE_DIRECTION = {"left": "right", "right": "left"}

ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh")

# Distance quantities, so a callout cannot name two different distances.
DISTANCE_WORDS = (
    "tenth of a mile",
    "point one miles",
    "quarter of a mile",
    "quarter mile",
    "half a mile",
    "half mile",
    "one mile",
    "two hundred meters",
    "four hundred meters",
    "eight hundred meters",
    "one kilometer",
    "one point five kilometers",
)


# What each line must still communicate, whatever else it does. Any one
# alternative satisfies the check.
REQUIRED_TOKENS: dict[str, tuple[tuple[str, ...], ...]] = {
    # Maneuvers: the direction word has to survive the rewrite.
    "turn_left": (("left",),),
    "turn_right": (("right",),),
    "keep_left": (("left",),),
    "keep_right": (("right",),),
    "exit_left": (("left",),),
    "exit_right": (("right",),),
    "go_straight": (("straight", "straight on", "ahead"),),
    "u_turn": (("u turn", "u-turn", "turn around"),),
    # Distances: the quantity has to survive intact. This is the one place a
    # preset absolutely cannot be playful. Both spellings of metre are accepted;
    # normalise() reduces "1.5" to "1 5", so digit forms are written that way.
    "in_tenth_mile": (
        ("tenth of a mile", "tenth mile", "point one miles", "point one mile"),
    ),
    "in_quarter_mile": (("quarter of a mile", "quarter mile"),),
    "in_half_mile": (("half a mile", "half mile"),),
    "in_one_mile": (("one mile", "a mile", "1 mile"),),
    "in_200_meters": (
        ("two hundred meters", "two hundred metres", "200 meters", "200 metres"),
    ),
    "in_400_meters": (
        ("four hundred meters", "four hundred metres", "400 meters", "400 metres"),
    ),
    "in_800_meters": (
        ("eight hundred meters", "eight hundred metres", "800 meters", "800 metres"),
    ),
    "in_1000_meters": (
        (
            "one kilometer",
            "one kilometre",
            "a kilometer",
            "a kilometre",
            "1 kilometer",
            "one thousand meters",
            "1000 meters",
        ),
    ),
    "in_1500_meters": (
        (
            "one point five kilometers",
            "one point five kilometres",
            "1 5 kilometers",
            "1 5 kilometres",
            "fifteen hundred meters",
            "1500 meters",
        ),
    ),
    # Roundabout ordinals: the number is the whole instruction.
    "exit_first": (("first",),),
    "exit_second": (("second",),),
    "exit_third": (("third",),),
    "exit_fourth": (("fourth",),),
    "exit_fifth": (("fifth",),),
    "exit_sixth": (("sixth",),),
    "exit_seventh": (("seventh",),),
    "roundabout": (("roundabout",),),
    # Arrival and alerts: the subject has to be identifiable.
    "arrived": (("arrived", "here", "we're there"),),
    "traffic_ahead": (("traffic",),),
    "accident_ahead": (("accident", "crash"),),
    "hazard_ahead": (("hazard", "something in the road", "obstruction"),),
    "speed_camera_ahead": (("speed camera",),),
    "red_light_camera_ahead": (("red light camera",),),
    "police_ahead": (("police",),),
}


def is_navigation_critical(phrase_id: str, weight: float) -> bool:
    """Whether mishearing this prompt changes what the driver does.

    Two ways in: the prompt carries a required token (a direction, a distance,
    an exit number), or it is heard often enough to matter. Drive-start
    greetings and the reroute chime are neither, which is why a preset can be
    exuberant there and sober everywhere else.
    """
    return phrase_id in REQUIRED_TOKENS or weight >= HIGH_FREQUENCY_WEIGHT


# Clear navigation speech, roughly 150 words per minute. Only ever an estimate:
# real duration depends on the voice, the model, and the punctuation. It exists
# so a user can see a pack will not fit *before* spending API calls, and the
# build compares it against measured reality afterwards.
CHARS_PER_SECOND = 14.0
MIN_CLIP_SECONDS = 0.45

# How far measured may drift from estimated before it is worth saying so.
ESTIMATE_TOLERANCE = 0.10


def estimate_seconds(text: str, *, speed: float = 1.0, padding: float = 0.0) -> float:
    """Rough spoken duration of one line, before encoding."""
    spoken = len(text) / (CHARS_PER_SECOND * max(speed, 0.01))
    return max(MIN_CLIP_SECONDS, spoken) + padding


class PresetError(SystemExit):
    """Raised for a preset that is malformed, unsafe, or navigationally unclear."""


@dataclass(frozen=True)
class Rights:
    """Why this character can be interpreted, and exactly how far that goes."""

    source_work: str
    author: str
    year: int
    pd_basis: str
    covered: tuple[str, ...]
    not_covered: tuple[str, ...]
    notes: str = ""

    @property
    def attribution(self) -> str:
        return f"{self.source_work} ({self.author}, {self.year})"


@dataclass(frozen=True)
class Preset:
    name: str
    label: str
    description: str
    provider: str
    voice: str
    direction: str
    lines: dict[str, str]
    rights: Rights
    provider_options: dict[str, Any] = field(default_factory=dict)
    # Merged on top of provider_options for prompts a driver must not mishear.
    # A character can be fast in its greetings and still has to be unambiguous
    # on "turn left". See is_navigation_critical.
    critical_provider_options: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    schema_version: int = SCHEMA_VERSION

    def options_for(self, phrase_id: str, weight: float) -> dict[str, Any]:
        """Provider options for one prompt, with the safety overrides applied."""
        options = dict(self.provider_options)
        if self.critical_provider_options and is_navigation_critical(phrase_id, weight):
            options.update(self.critical_provider_options)
        return options

    @property
    def total_chars(self) -> int:
        return sum(len(line) for line in self.lines.values())

    def text_for(self, phrase_id: str, fallback: str) -> str:
        return self.lines.get(phrase_id) or fallback


# --------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------


def presets_dir() -> Path:
    return paths.repo_root() / PRESETS_DIRNAME


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PresetError(f"Missing preset file: {path}") from None
    except json.JSONDecodeError as error:
        raise PresetError(f"Invalid JSON in {path}: {error}") from None
    if not isinstance(data, dict):
        raise PresetError(f"Expected a JSON object in {path}")
    return data


def _check_no_cloning(raw: dict[str, Any], errors: list[str]) -> None:
    """Refuse anything that would clone a performance.

    Public domain attaches to a work, never to a later performance of it. A
    preset that pointed the provider at reference audio would be cloning
    somebody's recording, which no amount of the book's age makes acceptable.
    """
    smuggled = sorted(CLONING_KEYS & set(raw))
    if smuggled:
        errors.append(
            f"top level has voice-cloning field(s): {', '.join(smuggled)}. "
            "Presets name a catalogue voice and describe delivery; they never "
            "clone a performance."
        )

    options = raw.get("provider_options")
    if isinstance(options, dict):
        smuggled_opts = sorted(CLONING_KEYS & set(options))
        if smuggled_opts:
            errors.append(
                f"provider_options contains voice-cloning key(s): "
                f"{', '.join(smuggled_opts)}. Presets never clone a performance."
            )


def _check_rights(raw: dict[str, Any], errors: list[str]) -> Rights | None:
    block = raw.get("rights")
    if not isinstance(block, dict):
        errors.append("missing a 'rights' block. Every preset must state its basis.")
        return None

    missing = [f for f in RIGHTS_FIELDS if not block.get(f)]
    if missing:
        errors.append(f"rights is missing: {', '.join(missing)}")
        return None

    for list_field in ("covered", "not_covered"):
        value = block.get(list_field)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"rights.{list_field} must be a non-empty list of strings.")
            return None

    try:
        year = int(block["year"])
    except (TypeError, ValueError):
        errors.append("rights.year must be a number.")
        return None

    return Rights(
        source_work=str(block["source_work"]),
        author=str(block["author"]),
        year=year,
        pd_basis=str(block["pd_basis"]),
        covered=tuple(block["covered"]),
        not_covered=tuple(block["not_covered"]),
        notes=str(block.get("notes", "")),
    )


def _ambiguity_errors(phrase_id: str, text: str) -> list[str]:
    """Catch a line that names more than one of the thing it is choosing between.

    Containing the right word is not enough. "Turn left, not right" contains
    "left" and is still a line a driver can act on wrongly, and at 70 km/h they
    will hear whichever word landed last.
    """
    problems: list[str] = []
    required = REQUIRED_TOKENS.get(phrase_id, ())
    flat = {token for alternatives in required for token in alternatives}

    # Left/right prompts must not mention the other side at all.
    for side, opposite in OPPOSITE_DIRECTION.items():
        if side in flat and contains_word(text, opposite):
            problems.append(
                f"{phrase_id}: {text!r} says both {side!r} and {opposite!r}. "
                "A driver hears whichever landed last."
            )

    # An ordinal prompt must name exactly one ordinal.
    named_ordinals = [word for word in ORDINALS if contains_word(text, word)]
    if any(word in flat for word in ORDINALS) and len(named_ordinals) > 1:
        problems.append(
            f"{phrase_id}: {text!r} names more than one exit "
            f"({', '.join(named_ordinals)})."
        )

    # A distance callout must name exactly one distance.
    if phrase_id.startswith("in_"):
        named = [word for word in DISTANCE_WORDS if contains_word(text, word)]
        # "quarter of a mile" also matches "quarter mile"; collapse near-dupes.
        distinct = {word.replace(" of a ", " ") for word in named}
        if len(distinct) > 1:
            problems.append(
                f"{phrase_id}: {text!r} names more than one distance "
                f"({', '.join(sorted(distinct))})."
            )

    return problems


def _check_lines(
    lines: dict[str, str],
    inventory: phrases_module.PhraseInventory,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Every prompt present, still unambiguous, and short enough to afford."""
    wanted = {phrase.id for phrase in inventory if phrase.in_waze_pack}

    missing = sorted(wanted - set(lines))
    if missing:
        errors.append(
            f"{len(missing)} phrase(s) have no line: {', '.join(missing[:8])}"
            + (" ..." if len(missing) > 8 else "")
        )

    unknown = sorted(set(lines) - {phrase.id for phrase in inventory})
    if unknown:
        errors.append(f"lines for unknown phrase id(s): {', '.join(unknown)}")

    by_id = {phrase.id: phrase for phrase in inventory}
    for phrase_id, line in sorted(lines.items()):
        phrase = by_id.get(phrase_id)
        if phrase is None:
            continue

        text = line.strip()
        if not text:
            errors.append(f"{phrase_id}: line is empty.")
            continue

        for alternatives in REQUIRED_TOKENS.get(phrase_id, ()):
            if not any(contains_word(text, token) for token in alternatives):
                errors.append(
                    f"{phrase_id}: {text!r} does not contain "
                    f"{' or '.join(repr(a) for a in alternatives)} as whole words. A "
                    "driver who has never heard of the character still has to know "
                    "what to do."
                )

        errors.extend(_ambiguity_errors(phrase_id, text))

        limit = (
            MAX_CHARS_HIGH_FREQUENCY
            if phrase.weight >= HIGH_FREQUENCY_WEIGHT
            else MAX_CHARS_OTHER
        )
        if len(text) > limit:
            errors.append(
                f"{phrase_id}: {len(text)} characters, over the {limit} limit for a "
                f"prompt of weight {phrase.weight}. Frequently-heard prompts stay "
                "short: they cost the most budget and grate first on repetition."
            )
        elif phrase.weight >= HIGH_FREQUENCY_WEIGHT and len(text) > limit * 0.8:
            warnings.append(f"{phrase_id}: {len(text)} chars, close to the {limit} limit.")


def validate_raw(
    raw: dict[str, Any],
    *,
    name: str,
    inventory: phrases_module.PhraseInventory,
) -> tuple[Preset | None, list[str], list[str]]:
    """Validate one preset, collecting every problem rather than the first."""
    errors: list[str] = []
    warnings: list[str] = []

    _check_no_cloning(raw, errors)
    rights = _check_rights(raw, errors)

    for required in ("label", "description", "provider", "voice", "direction"):
        if not str(raw.get(required, "")).strip():
            errors.append(f"missing or empty: {required}")

    lines = raw.get("lines")
    if not isinstance(lines, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in lines.items()
    ):
        errors.append("'lines' must be an object of phrase_id -> text.")
        lines = {}
    else:
        _check_lines(lines, inventory, errors, warnings)

    options = raw.get("provider_options", {})
    if not isinstance(options, dict):
        errors.append("provider_options must be an object.")
        options = {}

    critical = raw.get("critical_provider_options", {})
    if not isinstance(critical, dict):
        errors.append("critical_provider_options must be an object.")
        critical = {}
    smuggled_critical = sorted(CLONING_KEYS & set(critical))
    if smuggled_critical:
        errors.append(
            f"critical_provider_options contains voice-cloning key(s): "
            f"{', '.join(smuggled_critical)}. Presets never clone a performance."
        )

    if errors or rights is None:
        return None, errors, warnings

    return (
        Preset(
            name=name,
            label=str(raw["label"]),
            description=str(raw["description"]),
            provider=str(raw["provider"]),
            voice=str(raw["voice"]),
            direction=str(raw["direction"]),
            lines=dict(lines),
            rights=rights,
            provider_options=dict(options),
            critical_provider_options=dict(critical),
            notes=str(raw.get("notes", "")),
            schema_version=int(raw.get("schema_version", SCHEMA_VERSION)),
        ),
        errors,
        warnings,
    )


def load(name: str, *, phrases_path: Path | None = None) -> Preset:
    """Load and fully validate a preset, or exit explaining why it is unusable."""
    safe = paths.validate_pack_name(name)
    path = presets_dir() / f"{safe}.json"

    if not path.is_file():
        found = [preset.name for preset in list_presets(phrases_path=phrases_path)]
        hint = f" Available: {', '.join(found)}." if found else ""
        raise PresetError(f"No preset named {safe!r}.{hint}")

    inventory = phrases_module.load(phrases_path)
    preset, errors, _ = validate_raw(_read(path), name=safe, inventory=inventory)

    if preset is None:
        listed = "\n".join(f"  - {error}" for error in errors)
        raise PresetError(f"Preset {safe!r} is not usable:\n{listed}")
    return preset


def list_presets(*, phrases_path: Path | None = None) -> list[Preset]:
    """Every valid preset. Broken ones are skipped rather than fatal."""
    directory = presets_dir()
    if not directory.is_dir():
        return []

    inventory = phrases_module.load(phrases_path)
    found: list[Preset] = []
    for path in sorted(directory.glob("*.json")):
        try:
            preset, _, _ = validate_raw(
                _read(path), name=path.stem, inventory=inventory
            )
        except PresetError:
            continue
        if preset is not None:
            found.append(preset)
    return found


def estimate_durations(
    preset: Preset,
    inventory: phrases_module.PhraseInventory,
    *,
    padding: float = 0.0,
) -> dict[str, float]:
    """Estimated seconds per Waze filename, honouring the preset's speech rates."""
    estimates: dict[str, float] = {}
    for phrase in inventory:
        if not phrase.in_waze_pack:
            continue
        text = preset.text_for(phrase.id, "")
        if not text:
            continue
        options = preset.options_for(phrase.id, phrase.weight)
        speed = float(options.get("speed", 1.0) or 1.0)
        estimates[phrase.waze_filename] = estimate_seconds(
            text, speed=speed, padding=padding
        )
    return estimates


def check(name: str, *, phrases_path: Path | None = None) -> tuple[list[str], list[str]]:
    """Validate without loading. Returns (errors, warnings) for the contributor path."""
    safe = paths.validate_pack_name(name)
    path = presets_dir() / f"{safe}.json"
    if not path.is_file():
        return [f"No preset file at {path}"], []

    inventory = phrases_module.load(phrases_path)
    _, errors, warnings = validate_raw(_read(path), name=safe, inventory=inventory)
    return errors, warnings
