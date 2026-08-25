"""Validation: inventory shape, clip coverage, and audio properties.

The scaffold's validator checked that files existed. Existing is not the same as
correct: a stereo 22 kHz clip at -30 LUFS satisfies a file-existence check and
still ruins the pack. When ffprobe is available this also checks what is
actually inside each file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import (
    console,
    manifest as manifest_module,
    media,
    paths,
    phrases as phrases_module,
    sources as sources_module,
)
from ..config import PipelineConfig


@dataclass
class ValidateResult:
    present: list[phrases_module.Phrase] = field(default_factory=list)
    missing_required: list[phrases_module.Phrase] = field(default_factory=list)
    missing_optional: list[phrases_module.Phrase] = field(default_factory=list)
    property_problems: list[str] = field(default_factory=list)
    loudness_problems: list[str] = field(default_factory=list)
    source_problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (
            self.missing_required
            or self.property_problems
            or self.loudness_problems
            or self.source_problems
        )


def _check_properties(
    phrase: phrases_module.Phrase, path: Path, config: PipelineConfig
) -> list[str]:
    problems: list[str] = []
    try:
        info = media.probe(path)
    except media.MediaError as error:
        return [f"{phrase.id}: could not probe {path.name} ({error})"]

    if info.channels and info.channels != config.audio.channels:
        problems.append(
            f"{phrase.id}: {path.name} has {info.channels} channel(s), "
            f"expected {config.audio.channels}."
        )
    if info.sample_rate and info.sample_rate != config.audio.sample_rate:
        problems.append(
            f"{phrase.id}: {path.name} is {info.sample_rate} Hz, "
            f"expected {config.audio.sample_rate} Hz."
        )
    if info.duration and info.duration < 0.2:
        problems.append(f"{phrase.id}: {path.name} is only {info.duration:.2f}s long.")
    if info.duration and info.duration > 8.0:
        problems.append(
            f"{phrase.id}: {path.name} is {info.duration:.1f}s long, which is "
            "unusually long for a navigation prompt."
        )
    return problems


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    master_dir: Path | None = None,
    sources_path: Path | None = None,
    check_audio: bool = True,
) -> ValidateResult:
    console.step("Validate")

    phrases_path = phrases_path or paths.phrases_path()
    master_dir = master_dir or paths.master_dir()

    inventory = phrases_module.load(phrases_path)
    console.ok(f"Phrase inventory valid: {len(inventory)} phrase(s)")

    result = ValidateResult()
    have_ffprobe = media.find_tool("ffprobe") is not None
    if check_audio and not have_ffprobe:
        console.warn("ffprobe not found; skipping audio property checks.")

    for phrase in inventory:
        path = master_dir / phrase.filename
        if path.is_file():
            result.present.append(phrase)
            if check_audio and have_ffprobe:
                result.property_problems.extend(_check_properties(phrase, path, config))
        elif phrase.required:
            result.missing_required.append(phrase)
        else:
            result.missing_optional.append(phrase)

    # Loudness consistency, using what normalization recorded.
    build = manifest_module.Manifest.load()
    for record in build.loudness_outliers(config.loudness.target_lufs, config.loudness.tolerance_lu):
        if record.output_lufs is None:
            continue
        result.loudness_problems.append(
            f"{record.phrase_id}: final loudness {record.output_lufs:.1f} LUFS, "
            f"target {config.loudness.target_lufs} LUFS."
        )

    # Source CSV sanity, when the user has one.
    sources_path = sources_path or paths.sources_path()
    if sources_path.is_file():
        try:
            clips = sources_module.load(sources_path, known_phrase_ids=inventory.ids)
            console.ok(f"Source inventory valid: {len(clips)} row(s) in {sources_path.name}")
        except SystemExit as error:
            result.source_problems.append(str(error))

    required_count = len(inventory.required)
    console.info("")
    console.table(
        [
            ("Total phrases", str(len(inventory))),
            ("Required", str(required_count)),
            ("Optional", str(len(inventory) - required_count)),
            ("Final clips present", str(len(result.present))),
            ("Missing required", str(len(result.missing_required))),
            ("Missing optional", str(len(result.missing_optional))),
        ],
        headers=("Metric", "Value"),
    )

    console.bullets(
        "Missing required clips",
        [f"{p.id}: {p.label} ({p.filename})" for p in result.missing_required],
    )
    console.bullets(
        "Missing optional clips",
        [f"{p.id}: {p.label} ({p.filename})" for p in result.missing_optional],
    )
    console.bullets("Audio property problems", result.property_problems)
    console.bullets("Loudness outliers", result.loudness_problems)
    console.bullets("Source inventory problems", result.source_problems)

    if result.ok:
        console.info("\nValidation passed.")
    else:
        console.info("\nValidation failed.")

    return result
