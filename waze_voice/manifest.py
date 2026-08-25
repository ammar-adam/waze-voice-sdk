"""Build manifest: per-phrase provenance across the whole pipeline.

Without this, later steps have to guess. Normalization has to guess which take to
promote, export has to guess whether a clip came from real source media or from
TTS, and QA has no way to show you which clips are synthetic. The manifest
records that once, at the point each step actually knows it.

The file lives at ``audio/build-manifest.json`` and is Git-ignored along with the
rest of ``audio/``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import paths

SCHEMA_VERSION = 1

ORIGIN_EXTRACTED = "extracted"
ORIGIN_SYNTHESIZED = "synthesized"
ORIGIN_MANUAL = "manual"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class PhraseRecord:
    phrase_id: str
    origin: str = ""
    take: int | None = None
    source_path: str = ""
    source_start: float | None = None
    source_end: float | None = None
    extracted_path: str = ""
    processed_path: str = ""
    synthesized_path: str = ""
    master_path: str = ""
    clean_mode: str = ""
    synth_backend: str = ""
    duration_seconds: float | None = None
    input_lufs: float | None = None
    output_lufs: float | None = None
    output_true_peak_db: float | None = None
    gain_applied_db: float | None = None
    loudness_measured_on_padded: bool = False
    stages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated_at: str = ""

    def mark_stage(self, stage: str) -> None:
        if stage not in self.stages:
            self.stages.append(stage)
        self.updated_at = _now()

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


@dataclass
class Manifest:
    path: Path
    schema_version: int = SCHEMA_VERSION
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    phrases: dict[str, PhraseRecord] = field(default_factory=dict)

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "Manifest":
        path = path or paths.manifest_path()
        if not path.is_file():
            return cls(path=path)

        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # A corrupt manifest is a cache, not a source of truth. Start over
            # rather than blocking the whole pipeline on it.
            return cls(path=path)

        records: dict[str, PhraseRecord] = {}
        known = set(PhraseRecord.__dataclass_fields__)
        for phrase_id, raw in (data.get("phrases") or {}).items():
            if not isinstance(raw, dict):
                continue
            payload = {key: value for key, value in raw.items() if key in known}
            payload["phrase_id"] = phrase_id
            records[phrase_id] = PhraseRecord(**payload)

        return cls(
            path=path,
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
            phrases=records,
        )

    def save(self) -> Path:
        self.updated_at = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "phrases": {
                phrase_id: asdict(record) for phrase_id, record in sorted(self.phrases.items())
            },
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        return self.path

    # -- access ------------------------------------------------------------

    def record(self, phrase_id: str) -> PhraseRecord:
        """Get or create the record for a phrase."""
        existing = self.phrases.get(phrase_id)
        if existing is None:
            existing = PhraseRecord(phrase_id=phrase_id, updated_at=_now())
            self.phrases[phrase_id] = existing
        return existing

    def get(self, phrase_id: str) -> PhraseRecord | None:
        return self.phrases.get(phrase_id)

    def with_stage(self, stage: str) -> list[PhraseRecord]:
        return [record for record in self.phrases.values() if stage in record.stages]

    def synthesized_ids(self) -> set[str]:
        return {
            record.phrase_id
            for record in self.phrases.values()
            if record.origin == ORIGIN_SYNTHESIZED
        }

    def loudness_outliers(self, target_lufs: float, tolerance_lu: float) -> list[PhraseRecord]:
        """Clips whose final loudness drifted further than the tolerance allows."""
        outliers = []
        for record in self.phrases.values():
            if record.output_lufs is None:
                continue
            if abs(record.output_lufs - target_lufs) > tolerance_lu:
                outliers.append(record)
        return sorted(outliers, key=lambda record: record.phrase_id)

    def status_updates(self) -> dict[str, str]:
        """Derive phrases.json ``status`` values from what actually happened."""
        updates: dict[str, str] = {}
        for phrase_id, record in self.phrases.items():
            if "normalize" in record.stages and record.master_path:
                updates[phrase_id] = "final"
            elif record.origin == ORIGIN_SYNTHESIZED:
                updates[phrase_id] = "synthesized"
            elif "clean" in record.stages:
                updates[phrase_id] = "cleaned"
            elif "extract" in record.stages:
                updates[phrase_id] = "extracted"
        return updates
