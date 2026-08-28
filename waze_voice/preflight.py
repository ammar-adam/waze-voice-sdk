"""Everything checkable before spending an API call.

Generating a pack costs money and takes a minute. Almost everything that can be
wrong with it is knowable beforehand: whether the preset validates, whether the
filenames are ones Waze recognises, whether every line is still unambiguous as
navigation, and whether the whole thing will plausibly fit the size cap.

What is *not* knowable beforehand is real clip duration, which depends on the
voice and the model. So this reports an estimate, says plainly that it is an
estimate, and lists exactly what stays unverified until a real build runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import budget as budget_module
from . import console, providers, wazepack
from . import phrases as phrases_module
from . import presets as presets_module
from .config import PipelineConfig


@dataclass
class PresetReport:
    name: str
    label: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_seconds: float = 0.0
    estimated_bytes: int = 0
    utilisation: float = 0.0
    verdict: str = "ok"
    floored_clips: int = 0
    total_clips: int = 0
    rights_status: str = "public-domain"

    @property
    def ok(self) -> bool:
        return not self.errors and self.verdict != "over"


@dataclass
class PreflightReport:
    presets: list[PresetReport] = field(default_factory=list)
    inventory_problems: list[str] = field(default_factory=list)
    filename_problems: list[str] = field(default_factory=list)
    providers_ready: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            not self.inventory_problems
            and not self.filename_problems
            and all(report.ok for report in self.presets)
        )


def _check_filenames(inventory: phrases_module.PhraseInventory) -> list[str]:
    """Every mapped filename must be one Waze recognises, in both unit systems."""
    problems: list[str] = []
    claimed = {phrase.waze_filename for phrase in inventory if phrase.in_waze_pack}

    unknown = wazepack.unknown_filenames(claimed)
    if unknown:
        problems.append(
            f"phrases.json maps to filename(s) Waze does not recognise and will "
            f"silently ignore: {', '.join(sorted(unknown))}"
        )

    for units in (wazepack.UNITS_METRIC, wazepack.UNITS_IMPERIAL):
        missing = wazepack.core_filenames(units) - claimed
        if missing:
            problems.append(
                f"no phrase claims these core {units} prompts: {', '.join(sorted(missing))}"
            )
    return problems


def _estimate(
    preset: presets_module.Preset,
    inventory: phrases_module.PhraseInventory,
    config: PipelineConfig,
) -> budget_module.AllocationPlan:
    padding = (config.trim.lead_in_ms + config.trim.lead_out_ms) / 1000.0
    durations = presets_module.estimate_durations(preset, inventory, padding=padding)
    weights = {phrase.waze_filename: phrase.weight for phrase in inventory if phrase.in_waze_pack}

    specs = [
        budget_module.ClipSpec(
            filename=filename,
            source=Path(filename),
            duration=seconds,
            weight=weights.get(filename, 1.0),
        )
        for filename, seconds in durations.items()
    ]

    plan = budget_module.allocate(
        specs,
        budget_bytes=int(config.export.budget_bytes * config.export.target_utilisation)
        - config.export.overhead_reserve_bytes,
        strategy=config.export.strategy,
        min_kbps=config.export.min_kbps,
        max_kbps=config.export.max_kbps,
        sample_rate_policy=config.export.sample_rate_policy,
    )
    plan.budget_bytes = config.export.budget_bytes
    plan.target_utilisation = config.export.target_utilisation
    plan.fail_above_utilisation = config.export.fail_above_utilisation
    return plan


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    only: str | None = None,
) -> PreflightReport:
    console.step("Pre-flight")
    console.info("Everything checkable without an API call.")

    report = PreflightReport()

    # -- inventory ---------------------------------------------------------
    try:
        inventory = phrases_module.load(phrases_path)
        console.ok(f"Phrase inventory: {len(inventory)} phrases, schema valid")
    except SystemExit as error:
        report.inventory_problems.append(str(error))
        console.error(str(error))
        return report

    report.filename_problems = _check_filenames(inventory)
    if report.filename_problems:
        console.bullets("Waze filename problems", report.filename_problems)
    else:
        console.ok(
            f"Waze filenames: all {len(wazepack.VALID_FILENAMES)} slots claimed, "
            "both unit systems complete"
        )

    # -- providers ---------------------------------------------------------
    report.providers_ready = providers.available()
    if report.providers_ready:
        console.ok(f"API key present for: {', '.join(report.providers_ready)}")
    else:
        console.warn(
            "No provider API key set. Everything below still checks out fine; "
            "you just cannot build yet."
        )

    # -- presets -----------------------------------------------------------
    names = [only] if only else [p.name for p in presets_module.list_presets()]
    console.info("")

    rows = []
    for name in names:
        errors, warnings = presets_module.check(name, phrases_path=phrases_path)
        entry = PresetReport(name=name, label=name, errors=errors, warnings=warnings)

        if not errors:
            preset = presets_module.load(name, phrases_path=phrases_path)
            entry.label = preset.label
            entry.rights_status = preset.rights.status
            plan = _estimate(preset, inventory, config)
            entry.estimated_seconds = plan.total_duration
            entry.estimated_bytes = plan.total_predicted_bytes
            entry.utilisation = plan.utilisation
            entry.verdict = plan.verdict
            entry.total_clips = len(plan.allocations)
            entry.floored_clips = sum(
                1 for item in plan.allocations if item.bitrate_kbps <= config.export.min_kbps
            )

        report.presets.append(entry)
        rows.append(
            (
                name,
                entry.label,
                "PD" if entry.rights_status == "public-domain" else "in copyright",
                f"{entry.estimated_seconds:.0f}s",
                f"{entry.estimated_bytes / 1000:.0f} kB",
                f"{entry.utilisation * 100:.0f}%",
                entry.verdict if not errors else "INVALID",
                f"{entry.floored_clips}/{entry.total_clips}",
            )
        )

    console.table(
        rows,
        headers=(
            "Preset",
            "Label",
            "Rights",
            "Est audio",
            "Est size",
            "Est util",
            "Verdict",
            "At floor",
        ),
    )

    for entry in report.presets:
        if entry.errors:
            console.bullets(f"{entry.name}: not shippable", entry.errors)
        elif entry.warnings:
            console.bullets(f"{entry.name}: warnings", entry.warnings)

    # -- what this cannot tell you ----------------------------------------
    console.info("")
    console.info("Still unverified until a real build runs:")
    console.detail(
        "Clip duration. Sizes above assume "
        f"{presets_module.CHARS_PER_SECOND:.0f} characters per second of clear "
        "speech. A slower voice produces a larger pack, and the build reports the "
        f"measured drift when it exceeds {presets_module.ESTIMATE_TOLERANCE:.0%}."
    )
    console.detail(
        "How the lines actually sound. Nothing here listens. Run `wvs qa` after "
        "building, and listen to the chained_maneuvers route in particular."
    )
    console.detail(
        "Whether Waze accepts the upload. The size cap is community-reported, not "
        "documented, and rejection is silent. See docs/waze-import-workflow.md."
    )

    console.info("")
    if report.ok:
        console.ok("Pre-flight passed. Safe to spend API calls.")
    else:
        console.error("Pre-flight failed. Fix the above before building.")
    return report
