"""Source clip inventory: the CSV that maps phrase IDs to media timestamps."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from . import paths

REQUIRED_COLUMNS = {"phrase_id", "source_path", "start"}
OPTIONAL_COLUMNS = {"end", "duration", "take", "notes", "preferred", "gain_db"}
KNOWN_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

# `phrase_id__take3.wav`. The double underscore keeps take suffixes unambiguous:
# a single underscore would let the phrase `arrive` collide with `arrived_take1`
# when files are matched by prefix.
TAKE_SUFFIX = "__take"
_STEM_PATTERN = re.compile(rf"^(?P<phrase_id>.+?){re.escape(TAKE_SUFFIX)}(?P<take>\d+)$")

_TIMESTAMP = re.compile(
    r"^(?:(?:(?P<hours>\d+):)?(?P<minutes>\d+):)?(?P<seconds>\d+(?:\.\d+)?)$"
)


class SourceError(SystemExit):
    """Raised for malformed source inventories."""


@dataclass(frozen=True)
class SourceClip:
    phrase_id: str
    source_path: Path
    start: float
    end: float
    take: int
    notes: str = ""
    preferred: bool = False
    gain_db: float = 0.0
    row_number: int = 0

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def stem(self) -> str:
        return clip_stem(self.phrase_id, self.take)

    @property
    def filename(self) -> str:
        return f"{self.stem}.wav"


def clip_stem(phrase_id: str, take: int) -> str:
    return f"{phrase_id}{TAKE_SUFFIX}{take}"


def parse_stem(stem: str) -> tuple[str, int] | None:
    """Split ``turn_left__take2`` into ``("turn_left", 2)``."""
    match = _STEM_PATTERN.match(stem)
    if match is None:
        return None
    return match.group("phrase_id"), int(match.group("take"))


def parse_timestamp(value: str, *, field: str, row_number: int) -> float:
    """Accept ``HH:MM:SS.mmm``, ``MM:SS.mmm``, or plain seconds."""
    text = (value or "").strip()
    if not text:
        raise SourceError(f"Row {row_number}: '{field}' is required.")

    match = _TIMESTAMP.match(text)
    if match is None:
        raise SourceError(
            f"Row {row_number}: could not parse '{field}' value {text!r}. "
            "Use HH:MM:SS.mmm, MM:SS.mmm, or seconds."
        )

    hours = float(match.group("hours") or 0)
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds"))
    return hours * 3600 + minutes * 60 + seconds


def _parse_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _parse_float(value: str, *, field: str, row_number: int, default: float = 0.0) -> float:
    text = (value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        raise SourceError(f"Row {row_number}: '{field}' must be a number, got {text!r}.") from None


def load(
    path: Path | None = None,
    *,
    known_phrase_ids: set[str] | None = None,
    min_duration: float = 0.15,
    max_duration: float = 15.0,
) -> list[SourceClip]:
    """Parse the source CSV into validated clip records.

    Every row is checked before any ffmpeg work starts, so a typo in row 40 fails
    the run immediately instead of after 39 successful extractions.
    """
    path = path or paths.sources_path()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            rows = list(reader)
    except FileNotFoundError:
        raise SourceError(
            f"Missing source CSV: {path}\n"
            "Copy data/sources.sample.csv to your own file and point --sources at it."
        ) from None

    missing_columns = REQUIRED_COLUMNS - fieldnames
    if missing_columns:
        raise SourceError(
            f"{path} is missing required column(s): {', '.join(sorted(missing_columns))}"
        )
    if "end" not in fieldnames and "duration" not in fieldnames:
        raise SourceError(f"{path} must have either an 'end' or a 'duration' column.")

    unknown_columns = fieldnames - KNOWN_COLUMNS
    if unknown_columns:
        raise SourceError(
            f"{path} has unknown column(s): {', '.join(sorted(unknown_columns))}. "
            f"Known columns: {', '.join(sorted(KNOWN_COLUMNS))}"
        )

    clips: list[SourceClip] = []
    seen: set[tuple[str, int]] = set()

    for offset, row in enumerate(rows):
        row_number = offset + 2  # +1 for zero index, +1 for the header line
        phrase_id = (row.get("phrase_id") or "").strip()
        if not phrase_id:
            continue  # tolerate blank spacer rows

        if known_phrase_ids is not None and phrase_id not in known_phrase_ids:
            raise SourceError(
                f"Row {row_number}: unknown phrase_id {phrase_id!r}. "
                "Add it to config/phrases.json or fix the spelling."
            )

        raw_path = (row.get("source_path") or "").strip().strip('"')
        if not raw_path:
            raise SourceError(f"Row {row_number}: 'source_path' is required.")
        source_path = Path(raw_path).expanduser()

        start = parse_timestamp(row.get("start", ""), field="start", row_number=row_number)

        end_text = (row.get("end") or "").strip()
        duration_text = (row.get("duration") or "").strip()
        if end_text:
            end = parse_timestamp(end_text, field="end", row_number=row_number)
        elif duration_text:
            end = start + parse_timestamp(
                duration_text, field="duration", row_number=row_number
            )
        else:
            raise SourceError(f"Row {row_number}: provide either 'end' or 'duration'.")

        if end <= start:
            raise SourceError(
                f"Row {row_number}: 'end' ({end:.3f}s) must be after 'start' ({start:.3f}s)."
            )

        length = end - start
        if length < min_duration:
            raise SourceError(
                f"Row {row_number}: clip for {phrase_id} is {length:.3f}s, "
                f"shorter than the {min_duration}s minimum."
            )
        if length > max_duration:
            raise SourceError(
                f"Row {row_number}: clip for {phrase_id} is {length:.3f}s, "
                f"longer than the {max_duration}s maximum. Raise "
                "extract.max_duration_seconds in config/pipeline.json if that is intended."
            )

        take_text = (row.get("take") or "").strip() or "1"
        try:
            take = int(take_text)
        except ValueError:
            raise SourceError(
                f"Row {row_number}: 'take' must be a whole number, got {take_text!r}."
            ) from None
        if take < 1:
            raise SourceError(f"Row {row_number}: 'take' must be 1 or greater.")

        key = (phrase_id, take)
        if key in seen:
            raise SourceError(
                f"Row {row_number}: duplicate take {take} for phrase {phrase_id!r}. "
                "Give each row for a phrase a distinct take number."
            )
        seen.add(key)

        clips.append(
            SourceClip(
                phrase_id=phrase_id,
                source_path=source_path,
                start=start,
                end=end,
                take=take,
                notes=(row.get("notes") or "").strip(),
                preferred=_parse_bool(row.get("preferred", "")),
                gain_db=_parse_float(
                    row.get("gain_db", ""), field="gain_db", row_number=row_number
                ),
                row_number=row_number,
            )
        )

    _check_single_preferred(clips)
    return clips


def _check_single_preferred(clips: Iterable[SourceClip]) -> None:
    by_phrase: dict[str, list[SourceClip]] = {}
    for clip in clips:
        by_phrase.setdefault(clip.phrase_id, []).append(clip)

    for phrase_id, group in by_phrase.items():
        preferred = [clip for clip in group if clip.preferred]
        if len(preferred) > 1:
            takes = ", ".join(str(clip.take) for clip in preferred)
            raise SourceError(
                f"Phrase {phrase_id!r} marks more than one preferred take ({takes}). "
                "Mark exactly one, or none to default to the lowest take number."
            )


def preferred_take(clips: Iterable[SourceClip], phrase_id: str) -> int | None:
    """Return the take number the pipeline should carry downstream."""
    group = [clip for clip in clips if clip.phrase_id == phrase_id]
    if not group:
        return None
    for clip in group:
        if clip.preferred:
            return clip.take
    return min(clip.take for clip in group)
