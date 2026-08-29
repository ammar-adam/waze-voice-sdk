"""Phrase inventory loading and validation.

``config/phrases.json`` is the single source of truth for what a voice pack must
contain. Extraction, synthesis, normalization, QA, and export all read it
through this module.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths, wazepack

REQUIRED_FIELDS = {"id", "label", "required", "filename", "status"}
OPTIONAL_FIELDS = {
    "notes",
    "tts_text",
    "group",
    "order",
    "aliases",
    "waze_filename",
    "units",
    "weight",
}
KNOWN_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS

VALID_STATUSES = {"missing", "sourced", "extracted", "cleaned", "synthesized", "final"}

# Recording groups keep the export checklist readable. Order within the export
# follows group order first, then the per-phrase `order` value.
GROUP_ORDER = [
    "start",
    "distance",
    "maneuver",
    "lane",
    "roundabout",
    "arrival",
    "alert",
    "misc",
]


@dataclass(frozen=True)
class Phrase:
    id: str
    label: str
    required: bool
    filename: str
    status: str
    notes: str = ""
    tts_text: str = ""
    group: str = "misc"
    order: int | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    # The exact filename Waze expects for this prompt. Empty means the phrase is
    # not part of a Waze pack; the export step skips it.
    waze_filename: str = ""
    # "any", "metric", or "imperial". Distance callouts are two separate file
    # sets and a pack needs both to work in both unit systems.
    units: str = "any"
    # Share of the size budget this prompt deserves, relative to the others.
    # Higher means more bitrate. See waze_voice/budget.py.
    weight: float = 1.0

    @property
    def in_waze_pack(self) -> bool:
        return bool(self.waze_filename)

    @property
    def speech_text(self) -> str:
        """Text a TTS backend should speak. Falls back to the display label."""
        return self.tts_text.strip() or self.label.strip()

    @property
    def sort_key(self) -> tuple[int, int, str]:
        group_index = (
            GROUP_ORDER.index(self.group) if self.group in GROUP_ORDER else len(GROUP_ORDER)
        )
        return (group_index, self.order if self.order is not None else 10_000, self.id)


@dataclass
class PhraseInventory:
    phrases: list[Phrase]
    schema_version: int = 1

    def __iter__(self):
        return iter(self.phrases)

    def __len__(self) -> int:
        return len(self.phrases)

    @property
    def required(self) -> list[Phrase]:
        return [phrase for phrase in self.phrases if phrase.required]

    @property
    def optional(self) -> list[Phrase]:
        return [phrase for phrase in self.phrases if not phrase.required]

    @property
    def ids(self) -> set[str]:
        return {phrase.id for phrase in self.phrases}

    def get(self, phrase_id: str) -> Phrase | None:
        for phrase in self.phrases:
            if phrase.id == phrase_id:
                return phrase
        return None

    def require(self, phrase_id: str) -> Phrase:
        phrase = self.get(phrase_id)
        if phrase is None:
            raise SystemExit(f"Unknown phrase id: {phrase_id}")
        return phrase

    def in_export_order(self) -> list[Phrase]:
        return sorted(self.phrases, key=lambda phrase: phrase.sort_key)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing config file: {path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return data


def validate_raw(data: dict[str, Any]) -> tuple[list[Phrase], list[str]]:
    """Validate the raw inventory, returning parsed phrases plus error strings.

    Errors are collected rather than raised so the validator can report every
    problem in one pass instead of one per run.
    """
    errors: list[str] = []
    raw_phrases = data.get("phrases")

    if not isinstance(raw_phrases, list):
        return [], ["Top-level 'phrases' must be a list."]
    if not raw_phrases:
        return [], ["Top-level 'phrases' must not be empty."]

    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()
    seen_waze: set[str] = set()
    parsed: list[Phrase] = []

    for index, entry in enumerate(raw_phrases, start=1):
        location = f"phrases[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{location} must be an object.")
            continue

        missing = sorted(REQUIRED_FIELDS - entry.keys())
        if missing:
            errors.append(f"{location} missing field(s): {', '.join(missing)}")
            continue

        unknown = sorted(entry.keys() - KNOWN_FIELDS)
        if unknown:
            errors.append(f"{location} has unknown field(s): {', '.join(unknown)}")

        phrase_id = entry["id"]
        filename = entry["filename"]

        if not isinstance(phrase_id, str) or not phrase_id.strip():
            errors.append(f"{location}.id must be a non-empty string.")
            continue
        if phrase_id in seen_ids:
            errors.append(f"Duplicate phrase id: {phrase_id}")
        seen_ids.add(phrase_id)

        if not isinstance(filename, str) or not filename.strip():
            errors.append(f"{location}.filename must be a non-empty string.")
            filename = f"{phrase_id}.mp3"
        elif Path(filename).name != filename:
            errors.append(f"{location}.filename must be a bare filename, not a path: {filename}")
        elif filename in seen_filenames:
            errors.append(f"Duplicate filename: {filename}")
        else:
            seen_filenames.add(filename)

        if not isinstance(entry["required"], bool):
            errors.append(f"{location}.required must be true or false.")

        for text_field in ("label", "status"):
            value = entry[text_field]
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{location}.{text_field} must be a non-empty string.")

        status = str(entry.get("status", "missing"))
        if status not in VALID_STATUSES:
            errors.append(
                f"{location}.status '{status}' is not one of: {', '.join(sorted(VALID_STATUSES))}"
            )

        group = str(entry.get("group", "misc"))
        if group not in GROUP_ORDER:
            errors.append(f"{location}.group '{group}' is not one of: {', '.join(GROUP_ORDER)}")

        order = entry.get("order")
        if order is not None and not isinstance(order, int):
            errors.append(f"{location}.order must be an integer when present.")
            order = None

        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            errors.append(f"{location}.aliases must be a list of strings.")
            aliases = []

        waze_filename = str(entry.get("waze_filename", "") or "")
        if waze_filename and waze_filename in seen_waze:
            errors.append(
                f"Two phrases both claim the Waze slot {waze_filename}; only one "
                "would survive into the pack."
            )
        elif waze_filename:
            seen_waze.add(waze_filename)

        if waze_filename and not wazepack.is_valid(waze_filename):
            errors.append(
                f"{location}.waze_filename {waze_filename!r} is not a filename Waze "
                "recognises. Waze silently ignores unknown names, so this prompt "
                "would be missing from the finished pack. See waze_voice/wazepack.py."
            )

        units = str(entry.get("units", "any"))
        if units not in (wazepack.UNITS_ANY, wazepack.UNITS_METRIC, wazepack.UNITS_IMPERIAL):
            errors.append(f"{location}.units {units!r} must be 'any', 'metric', or 'imperial'.")
        elif waze_filename and wazepack.is_valid(waze_filename):
            expected = wazepack.BY_FILENAME[waze_filename].units
            if units != expected:
                errors.append(
                    f"{location}.units is {units!r} but {waze_filename} is a {expected!r} slot."
                )

        weight = entry.get("weight", 1.0)
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0:
            errors.append(f"{location}.weight must be a non-negative number.")
            weight = 1.0

        parsed.append(
            Phrase(
                id=phrase_id.strip(),
                label=str(entry["label"]).strip(),
                required=bool(entry["required"]),
                filename=filename.strip(),
                status=status,
                notes=str(entry.get("notes", "")),
                tts_text=str(entry.get("tts_text", "")),
                group=group,
                order=order,
                aliases=tuple(aliases),
                waze_filename=waze_filename,
                units=units,
                weight=float(weight),
            )
        )

    return parsed, errors


def load(path: Path | None = None, *, strict: bool = True) -> PhraseInventory:
    """Load the inventory. With ``strict`` set, any validation error exits."""
    path = path or paths.phrases_path()
    data = _read_json(path)
    parsed, errors = validate_raw(data)

    if errors and strict:
        message = "\n".join(f"  - {error}" for error in errors)
        raise SystemExit(f"Phrase inventory errors in {path}:\n{message}")

    return PhraseInventory(
        phrases=parsed,
        schema_version=int(data.get("schema_version", 1)),
    )


def set_statuses(path: Path, updates: dict[str, str]) -> int:
    """Write new ``status`` values back into the inventory, preserving layout.

    Pipeline steps record their own progress here so a fresh clone can tell at a
    glance which phrases are sourced, synthesized, or final.
    """
    if not updates:
        return 0

    data = _read_json(path)
    raw_phrases = data.get("phrases")
    if not isinstance(raw_phrases, list):
        raise SystemExit(f"Cannot update statuses: 'phrases' is not a list in {path}")

    changed = 0
    for entry in raw_phrases:
        if not isinstance(entry, dict):
            continue
        phrase_id = str(entry.get("id", ""))
        new_status = updates.get(phrase_id)
        if new_status and new_status != entry.get("status"):
            entry["status"] = new_status
            changed += 1

    if changed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return changed


def filter_ids(inventory: PhraseInventory, only: Iterable[str] | None) -> list[Phrase]:
    """Narrow an inventory to an explicit id list, validating every id."""
    if not only:
        return list(inventory.phrases)

    wanted = [value.strip() for value in only if value.strip()]
    unknown = [value for value in wanted if value not in inventory.ids]
    if unknown:
        raise SystemExit(f"Unknown phrase id(s): {', '.join(unknown)}")
    return [phrase for phrase in inventory.phrases if phrase.id in set(wanted)]
