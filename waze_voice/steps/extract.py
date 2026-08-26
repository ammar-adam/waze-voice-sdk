"""Step 1: cut phrase clips out of the user's source media with ffmpeg."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .. import console, media, paths, sources
from .. import manifest as manifest_module
from .. import phrases as phrases_module
from ..config import PipelineConfig


@dataclass
class ExtractResult:
    extracted: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    phrases_without_sources: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def _verify_sources_exist(clips: Sequence[sources.SourceClip]) -> None:
    """Fail before any ffmpeg work if a media file is missing.

    All missing paths are reported together; discovering them one failed
    extraction at a time is needlessly slow when a whole drive is unmounted.
    """
    missing: list[str] = []
    seen: set[Path] = set()
    for clip in clips:
        if clip.source_path in seen:
            continue
        seen.add(clip.source_path)
        if not clip.source_path.is_file():
            missing.append(f"row {clip.row_number}: {clip.source_path}")

    if missing:
        listed = "\n".join(f"  - {item}" for item in missing)
        raise SystemExit(f"Source media file(s) not found:\n{listed}")


def _verify_within_source(clip: sources.SourceClip) -> str | None:
    """Return a warning if the requested cut runs past the end of the media."""
    try:
        info = media.probe(clip.source_path)
    except media.MediaError as error:
        return f"{clip.phrase_id}: could not probe {clip.source_path.name} ({error})"

    if info.duration and clip.end > info.duration + 0.05:
        return (
            f"{clip.phrase_id} take {clip.take}: end {clip.end:.2f}s is past the end of "
            f"{clip.source_path.name} ({info.duration:.2f}s). The clip will be short."
        )
    return None


def run(
    *,
    config: PipelineConfig,
    sources_path: Path | None = None,
    phrases_path: Path | None = None,
    output_dir: Path | None = None,
    only: Iterable[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> ExtractResult:
    console.step("Extract")

    inventory = phrases_module.load(phrases_path)
    clips = sources.load(
        sources_path,
        known_phrase_ids=inventory.ids,
        min_duration=config.extract.min_duration_seconds,
        max_duration=config.extract.max_duration_seconds,
    )

    wanted = {phrase.id for phrase in phrases_module.filter_ids(inventory, only)}
    clips = [clip for clip in clips if clip.phrase_id in wanted]

    result = ExtractResult()
    if not clips:
        console.warn("No source rows matched. Nothing to extract.")
        result.phrases_without_sources = sorted(
            phrase.id for phrase in inventory if phrase.id in wanted
        )
        return result

    _verify_sources_exist(clips)

    output_dir = output_dir or paths.extracted_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = manifest_module.Manifest.load()

    for clip in clips:
        destination = output_dir / clip.filename

        if destination.is_file() and not force:
            console.detail(f"skip (exists) {destination.name}")
            result.skipped.append(destination)
            continue

        warning = _verify_within_source(clip)
        if warning:
            console.warn(warning)

        if dry_run:
            console.detail(
                f"would cut {clip.phrase_id} take {clip.take}: "
                f"{clip.start:.3f}-{clip.end:.3f}s from {clip.source_path.name}"
            )
            continue

        filters: list[str] = []
        if clip.gain_db:
            filters.append(f"volume={clip.gain_db}dB")
        filters += media.fade_chain(config.extract.edge_fade_ms, clip.duration)

        try:
            media.cut(
                clip.source_path,
                destination,
                start=clip.start,
                duration=clip.duration,
                preroll=config.extract.seek_preroll_seconds,
                filters=filters,
                sample_rate=config.audio.sample_rate,
                channels=config.audio.channels,
            )
        except media.MediaError as error:
            console.error(f"{clip.phrase_id} take {clip.take}: {error}")
            result.failures.append(clip.phrase_id)
            continue

        record = manifest.record(clip.phrase_id)
        record.origin = manifest_module.ORIGIN_EXTRACTED
        record.take = clip.take
        record.source_path = str(clip.source_path)
        record.source_start = clip.start
        record.source_end = clip.end
        record.extracted_path = str(destination)
        record.duration_seconds = clip.duration
        record.mark_stage("extract")

        console.ok(f"{destination.name}  ({clip.duration:.2f}s)")
        result.extracted.append(destination)

    if not dry_run:
        manifest.save()

    sourced_ids = {clip.phrase_id for clip in clips}
    result.phrases_without_sources = sorted(
        phrase.id for phrase in inventory if phrase.id in wanted and phrase.id not in sourced_ids
    )

    console.info(
        f"Extracted {len(result.extracted)} clip(s), skipped {len(result.skipped)} existing."
    )
    if result.phrases_without_sources:
        console.bullets(
            "Phrases with no source rows (candidates for TTS or manual recording):",
            result.phrases_without_sources,
        )

    return result
