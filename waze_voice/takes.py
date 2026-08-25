"""Resolving which audio file represents a phrase at any point in the pipeline.

The scaffold matched clips with ``glob(f"{phrase_id}*")``. That is a prefix
match, so the phrase ``arrive`` would happily claim ``arrived__take1.wav``, and
``take10`` sorted ahead of ``take2``. Both bugs are silent: you get a finished
voice pack that says the wrong thing. Matching is exact here instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import paths, sources

# Search order matters: a cleaned clip beats a synthesized one, and both beat the
# raw extraction, because that is the order of increasing rawness.
SEARCH_ORDER = ("processed", "synthesized", "extracted")

AUDIO_EXTENSIONS = (".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg")


@dataclass(frozen=True)
class ClipCandidate:
    path: Path
    origin: str
    phrase_id: str
    take: int | None

    @property
    def is_synthesized(self) -> bool:
        return self.origin == "synthesized"


def _candidates_in(directory: Path, phrase_id: str) -> list[ClipCandidate]:
    """Every file in ``directory`` that belongs to ``phrase_id``, exactly matched."""
    if not directory.is_dir():
        return []

    origin = directory.name
    found: list[ClipCandidate] = []

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        stem = path.stem
        if stem == phrase_id:
            found.append(ClipCandidate(path=path, origin=origin, phrase_id=phrase_id, take=None))
            continue

        parsed = sources.parse_stem(stem)
        if parsed is not None and parsed[0] == phrase_id:
            found.append(
                ClipCandidate(path=path, origin=origin, phrase_id=phrase_id, take=parsed[1])
            )

    # Numeric take order, so take2 sorts before take10.
    found.sort(key=lambda candidate: (candidate.take is None, candidate.take or 0))
    return found


def find(
    phrase_id: str,
    *,
    audio_root: Path | None = None,
    preferred_take: int | None = None,
) -> ClipCandidate | None:
    """Resolve the file that should represent ``phrase_id`` downstream.

    ``preferred_take`` comes from the source CSV, so a user who marks take 3 as
    the good one gets take 3 even though take 1 exists.
    """
    audio_root = audio_root or paths.audio_root()

    for directory_name in SEARCH_ORDER:
        candidates = _candidates_in(audio_root / directory_name, phrase_id)
        if not candidates:
            continue

        if preferred_take is not None:
            exact = [c for c in candidates if c.take == preferred_take]
            if exact:
                return exact[0]

        return candidates[0]

    return None


def find_all(phrase_id: str, *, audio_root: Path | None = None) -> list[ClipCandidate]:
    """Every candidate for a phrase across every stage, in search order."""
    audio_root = audio_root or paths.audio_root()
    results: list[ClipCandidate] = []
    for directory_name in SEARCH_ORDER:
        results.extend(_candidates_in(audio_root / directory_name, phrase_id))
    return results


def missing_phrase_ids(
    phrase_ids: list[str],
    *,
    audio_root: Path | None = None,
) -> list[str]:
    """Phrase IDs with no usable audio anywhere in the pipeline."""
    audio_root = audio_root or paths.audio_root()
    return [
        phrase_id
        for phrase_id in phrase_ids
        if find(phrase_id, audio_root=audio_root) is None
    ]
