"""Validation: inventory shape, pack completeness, audio properties, size budget.

Three separate questions, and the interesting one is the middle:

1. Is ``config/phrases.json`` internally coherent?
2. Does the pack it describes satisfy **Waze's** requirements, in both unit
   systems?
3. Are the finished files actually the audio they claim to be, and will the pack
   fit in Waze's aggregate size budget?

Checking coverage against our own inventory only answers a question we set
ourselves. A pack can be 100% complete by that measure and still arrive on a
phone missing every metric distance callout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import budget as budget_module
from .. import console, media, paths, wazepack
from .. import manifest as manifest_module
from .. import phrases as phrases_module
from .. import sources as sources_module
from ..config import PipelineConfig


@dataclass
class ValidateResult:
    present: list[phrases_module.Phrase] = field(default_factory=list)
    missing_required: list[phrases_module.Phrase] = field(default_factory=list)
    missing_optional: list[phrases_module.Phrase] = field(default_factory=list)
    property_problems: list[str] = field(default_factory=list)
    loudness_problems: list[str] = field(default_factory=list)
    source_problems: list[str] = field(default_factory=list)
    pack_problems: list[str] = field(default_factory=list)
    # Waze slots with no phrase claiming them at all.
    unclaimed_slots: list[str] = field(default_factory=list)
    metric_missing: list[str] = field(default_factory=list)
    imperial_missing: list[str] = field(default_factory=list)
    estimated_pack_bytes: int = 0
    budget_bytes: int = 0

    @property
    def over_budget(self) -> bool:
        return self.budget_bytes > 0 and self.estimated_pack_bytes > self.budget_bytes

    @property
    def ok(self) -> bool:
        return not (
            self.missing_required
            or self.property_problems
            or self.loudness_problems
            or self.source_problems
            or self.pack_problems
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
            "unusually long for a navigation prompt and expensive against the "
            "0.8 MB pack budget."
        )
    return problems


def _check_pack_coverage(
    inventory: phrases_module.PhraseInventory,
    master_dir: Path,
    result: ValidateResult,
) -> None:
    """Compare what exists against what Waze actually asks for."""
    claimed = {phrase.waze_filename for phrase in inventory if phrase.in_waze_pack}
    result.unclaimed_slots = sorted(wazepack.VALID_FILENAMES - claimed)

    have: set[str] = set()
    for phrase in inventory:
        if phrase.in_waze_pack and (master_dir / phrase.filename).is_file():
            have.add(phrase.waze_filename)

    for units, bucket in (
        (wazepack.UNITS_METRIC, result.metric_missing),
        (wazepack.UNITS_IMPERIAL, result.imperial_missing),
    ):
        bucket.extend(sorted(wazepack.core_filenames(units) - have))

    # A pack that covers one unit system and not the other is the failure mode
    # nobody notices until they are driving in the other one.
    metric_distance = {
        slot.filename for slot in wazepack.SLOTS if slot.units == wazepack.UNITS_METRIC
    }
    imperial_distance = {
        slot.filename for slot in wazepack.SLOTS if slot.units == wazepack.UNITS_IMPERIAL
    }
    has_metric = bool(have & metric_distance)
    has_imperial = bool(have & imperial_distance)

    if has_metric and not has_imperial:
        result.pack_problems.append(
            "Pack has metric distance callouts but no imperial ones. On a phone set "
            "to miles, every distance prompt falls back to the default Waze voice."
        )
    elif has_imperial and not has_metric:
        result.pack_problems.append(
            "Pack has imperial distance callouts but no metric ones. On a phone set "
            "to kilometers, every distance prompt falls back to the default Waze voice."
        )
    elif not has_metric and not has_imperial:
        result.pack_problems.append(
            "Pack has no distance callouts in either unit system."
        )


def _estimate_pack_size(
    inventory: phrases_module.PhraseInventory,
    master_dir: Path,
    config: PipelineConfig,
    result: ValidateResult,
) -> None:
    """Predict the packed size before the export step runs.

    Cheap early warning: if the pack cannot fit even at the allocator's best
    effort, that is worth knowing at validate time rather than after an upload
    is silently rejected.
    """
    specs: list[budget_module.ClipSpec] = []
    for phrase in inventory:
        if not phrase.in_waze_pack:
            continue
        source = master_dir / phrase.filename
        if not source.is_file():
            continue
        try:
            duration = media.duration_seconds(source)
        except media.MediaError:
            continue
        specs.append(
            budget_module.ClipSpec(
                filename=phrase.waze_filename,
                source=source,
                duration=duration,
                weight=phrase.weight,
            )
        )

    result.budget_bytes = config.export.budget_bytes
    if not specs:
        return

    plan = budget_module.allocate(
        specs,
        budget_bytes=max(0, config.export.budget_bytes - config.export.overhead_reserve_bytes),
        strategy=config.export.strategy,
        min_kbps=config.export.min_kbps,
        max_kbps=config.export.max_kbps,
        sample_rate_policy=config.export.sample_rate_policy,
    )
    result.estimated_pack_bytes = plan.total_predicted_bytes

    if result.estimated_pack_bytes > config.export.budget_bytes:
        over = result.estimated_pack_bytes - config.export.budget_bytes
        result.pack_problems.append(
            f"Estimated pack size {result.estimated_pack_bytes / 1000:.1f} kB exceeds "
            f"Waze's {config.export.budget_bytes / 1000:.1f} kB budget by "
            f"{over / 1000:.1f} kB, even at the minimum bitrate. Shorten the longest "
            "clips or drop optional prompts."
        )


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
        console.warn("ffprobe not found; skipping audio property and size checks.")

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

    _check_pack_coverage(inventory, master_dir, result)
    if check_audio and have_ffprobe:
        _estimate_pack_size(inventory, master_dir, config, result)

    build = manifest_module.Manifest.load()
    for record in build.loudness_outliers(
        config.loudness.target_lufs, config.loudness.tolerance_lu
    ):
        if record.output_lufs is None:
            continue
        result.loudness_problems.append(
            f"{record.phrase_id}: final loudness {record.output_lufs:.1f} LUFS, "
            f"target {config.loudness.target_lufs} LUFS."
        )

    sources_path = sources_path or paths.sources_path()
    if sources_path.is_file():
        try:
            clips = sources_module.load(sources_path, known_phrase_ids=inventory.ids)
            console.ok(f"Source inventory valid: {len(clips)} row(s) in {sources_path.name}")
        except SystemExit as error:
            result.source_problems.append(str(error))

    _print_summary(inventory, result, config)
    return result


def _print_summary(
    inventory: phrases_module.PhraseInventory,
    result: ValidateResult,
    config: PipelineConfig,
) -> None:
    required_count = len(inventory.required)
    metric_core = len(wazepack.core_filenames(wazepack.UNITS_METRIC))
    imperial_core = len(wazepack.core_filenames(wazepack.UNITS_IMPERIAL))

    console.info("")
    console.table(
        [
            ("Phrases in inventory", str(len(inventory))),
            ("Required", str(required_count)),
            ("Final clips present", str(len(result.present))),
            ("Missing required", str(len(result.missing_required))),
            ("Missing optional", str(len(result.missing_optional))),
            (
                "Waze core prompts, metric",
                f"{metric_core - len(result.metric_missing)}/{metric_core}",
            ),
            (
                "Waze core prompts, imperial",
                f"{imperial_core - len(result.imperial_missing)}/{imperial_core}",
            ),
            (
                "Estimated pack size",
                f"{result.estimated_pack_bytes / 1000:.1f} kB of "
                f"{result.budget_bytes / 1000:.1f} kB"
                if result.estimated_pack_bytes
                else "not estimated",
            ),
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
    console.bullets("Waze core prompts missing, metric", result.metric_missing)
    console.bullets("Waze core prompts missing, imperial", result.imperial_missing)
    console.bullets(
        "Waze slots no phrase claims (they will simply be absent)",
        result.unclaimed_slots,
    )
    console.bullets("Pack problems", result.pack_problems)
    console.bullets("Audio property problems", result.property_problems)
    console.bullets("Loudness outliers", result.loudness_problems)
    console.bullets("Source inventory problems", result.source_problems)

    if result.ok:
        console.info("\nValidation passed.")
    else:
        console.info("\nValidation failed.")
