"""Step 6: build a pack Waze will actually accept.

The creation device and the consumption device are decoupled. Waze stores custom
voice packs server-side and hands out a share link; opening that link on a phone
pulls the pack down. So a pack can be built on a PC from MP3 files and never
touch the in-app recorder.

Two things decide whether that works, and both fail quietly:

**Exact filenames.** Waze matches on filename. Anything not on its list is
ignored without complaint, so a near-miss produces a pack that is silently
missing that prompt.

**The aggregate size budget.** Roughly 0.8 MB across every MP3 in the pack.
Exceeding it is rejected server-side, which surfaces as a share button that greys
out after saving, or a link that downloads and then plays silence. Neither says
"too big". So this step measures the finished pack against the budget and says so
before the user attempts an upload.

Sources for both: https://github.com/pipeeeeees/waze-voicepack-links
(``mp3_upload/``), and that repository's discussion #31.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import (
    budget as budget_module,
    console,
    manifest as manifest_module,
    media,
    paths,
    phrases as phrases_module,
    wazepack,
)
from ..config import PipelineConfig

PACK_DIRNAME = "pack"
CHECKLIST_NAME = "UPLOAD_CHECKLIST.md"
GUIDE_NAME = "HOW-TO-UPLOAD.md"
MANIFEST_NAME = "pack-manifest.json"
README_NAME = "README.md"

# How many encode-measure-reduce passes before giving up. Each pass removes one
# ladder rung from one clip, so this is generous.
MAX_CORRECTION_PASSES = 40


@dataclass
class PackFile:
    slot: wazepack.WazeSlot
    phrase: phrases_module.Phrase
    source: Path
    destination: Path
    allocation: budget_module.Allocation

    @property
    def bytes(self) -> int:
        return self.allocation.bytes


@dataclass
class ExportResult:
    files: list[PackFile] = field(default_factory=list)
    plan: budget_module.AllocationPlan | None = None
    missing_core: list[phrases_module.Phrase] = field(default_factory=list)
    missing_optional: list[phrases_module.Phrase] = field(default_factory=list)
    dropped_for_budget: list[str] = field(default_factory=list)
    units: str = "both"
    checklist: Path | None = None
    guide: Path | None = None
    pack_manifest: Path | None = None
    corrections: int = 0

    @property
    def total_bytes(self) -> int:
        return sum(item.bytes for item in self.files)

    @property
    def over_budget(self) -> bool:
        return self.plan is not None and not self.plan.fits

    @property
    def ok(self) -> bool:
        return not self.missing_core and not self.over_budget


# --------------------------------------------------------------------------
# Gathering
# --------------------------------------------------------------------------


def _wanted_slots(units: str) -> list[wazepack.WazeSlot]:
    if units == "both":
        return list(wazepack.SLOTS)
    return list(wazepack.slots_for_units(units))


def _clear(export_dir: Path) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    for path in export_dir.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink()


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


def _encode(item: PackFile) -> int:
    """Encode one clip at its allocated bitrate. Returns the size on disk."""
    media.render(
        item.source,
        item.destination,
        sample_rate=item.allocation.sample_rate,
        channels=1,
        codec="libmp3lame",
        bitrate=f"{item.allocation.bitrate_kbps}k",
        # Waze reads these files by name; tags are pure overhead against a
        # budget measured in hundreds of kilobytes.
        extra_output_args=("-map_metadata", "-1", "-write_xing", "0", "-id3v2_version", "0"),
    )
    size = item.destination.stat().st_size
    item.allocation.actual_bytes = size
    return size


def _encode_all(files: list[PackFile]) -> int:
    total = 0
    for item in files:
        total += _encode(item)
    return total


def _correct_overshoot(
    files: list[PackFile],
    plan: budget_module.AllocationPlan,
    config: PipelineConfig,
) -> int:
    """Bring the measured pack under budget after encoding overshoot.

    Predicted size is bitrate times duration; the real file also carries frame
    headers and padding. That gap is small but it is always in the wrong
    direction, so the pack is measured and then walked down until it fits.
    """
    by_name = {item.allocation.filename: item for item in files}
    passes = 0

    while plan.total_bytes > plan.budget_bytes and passes < MAX_CORRECTION_PASSES:
        reduced = budget_module.reduce_to_fit(plan, min_kbps=config.export.min_kbps)
        if reduced is None:
            break
        item = by_name.get(reduced.filename)
        if item is None:
            break
        _encode(item)
        passes += 1

    return passes


# --------------------------------------------------------------------------
# Written output
# --------------------------------------------------------------------------


def _fmt_kb(value: int) -> str:
    return f"{value / 1000:.1f} kB"


def _checklist(result: ExportResult, config: PipelineConfig) -> str:
    plan = result.plan
    assert plan is not None

    lines = [
        "# Waze voice pack upload checklist",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Size budget",
        "",
        f"- Pack total: **{_fmt_kb(result.total_bytes)}** across {len(result.files)} file(s)",
        f"- Waze budget: {_fmt_kb(plan.budget_bytes)}",
        f"- Headroom: {_fmt_kb(plan.headroom_bytes)} ({plan.utilisation * 100:.1f}% used)",
        f"- Allocation strategy: `{plan.strategy}`",
        "",
    ]

    if result.over_budget:
        lines += [
            "> **This pack is over budget and Waze will reject it.** The rejection is",
            "> silent: the share button greys out after saving, or the link downloads",
            "> and plays nothing. Shorten the longest clips, drop optional prompts, or",
            "> export a single unit system. See the size table below.",
            "",
        ]
    else:
        lines += [
            "This pack is within budget. Waze should accept it.",
            "",
        ]

    lines += [
        "## Upload",
        "",
        f"1. Read `{GUIDE_NAME}` first if you have not done this before.",
        f"2. Upload the contents of `{PACK_DIRNAME}/` using the community tool at",
        "   <https://github.com/pipeeeeees/waze-voicepack-links> (`mp3_upload/`).",
        "3. It returns a share link of the form `https://waze.com/ul?acvp=<UUID>`.",
        "4. Open that link on the phone you navigate with. Waze downloads the pack.",
        "5. Drive or simulate a route and confirm the prompts fire.",
        "",
        "Keep the UUID. The pack can be re-downloaded later from",
        "`https://voice-prompts-ipv6.waze.com/<UUID>.tar.gz`.",
        "",
        "## Files in this pack",
        "",
        "| Waze file | Phrase | Say | Length | kbps | Size | Source |",
        "| --------- | ------ | --- | ------ | ---- | ---- | ------ |",
    ]

    ordered = sorted(
        result.files, key=lambda item: wazepack.FILENAME_ORDER.get(item.slot.filename, 999)
    )
    for item in ordered:
        origin = "synthesized" if item.phrase.status == "synthesized" else "source media"
        rate = f"{item.allocation.bitrate_kbps}"
        if item.allocation.sample_rate != budget_module.SAMPLE_RATE_FULL:
            rate += f" @{item.allocation.sample_rate // 1000}k"
        lines.append(
            f"| `{item.slot.filename}` | {item.phrase.label} | "
            f'"{item.phrase.speech_text}" | {item.allocation.duration:.2f}s | '
            f"{rate} | {_fmt_kb(item.bytes)} | {origin} |"
        )

    if result.missing_core:
        lines += [
            "",
            "## Missing, and worth fixing",
            "",
            "Waze accepts an incomplete pack and falls back to its default voice for",
            "anything absent, which is more jarring mid-drive than it sounds. These are",
            "the ones that matter:",
            "",
        ]
        for phrase in result.missing_core:
            lines.append(
                f"- [ ] `{phrase.waze_filename}` - {phrase.label} "
                f'("{phrase.speech_text}")'
            )

    if result.missing_optional:
        lines += ["", "## Missing, optional", ""]
        for phrase in result.missing_optional:
            lines.append(f"- `{phrase.waze_filename}` - {phrase.label}")

    if result.dropped_for_budget:
        lines += [
            "",
            "## Dropped to fit the budget",
            "",
        ]
        for name in result.dropped_for_budget:
            lines.append(f"- `{name}`")

    if result.units != "both":
        lines += [
            "",
            f"## Single unit system: {result.units}",
            "",
            f"This pack carries only the {result.units} distance callouts. On a phone set",
            "to the other unit system, distance prompts fall back to the default Waze",
            "voice while everything else uses yours. Export with `--units both` to cover",
            "both, budget permitting.",
        ]

    lines.append("")
    return "\n".join(lines)


def _guide() -> str:
    return """# How to get this pack onto a phone

## The short version

Waze stores custom voice packs on its servers, not on the device. You build the
pack anywhere, upload it, get a share link, and open that link on the phone. The
in-app recorder is one way to create a pack; it is not the only way, and it is
not the one that preserves your audio quality.

## What is confirmed

- **The Waze mobile app is record-only.** There is no MP3 upload in the app, on
  either iOS or Android. Looking for one is a dead end.
- **Packs live server-side and travel as links.** The share link format is
  `https://waze.com/ul?acvp=<UUID>`. Opening it on a phone with Waze installed
  makes Waze fetch the pack.
- **Any pack can be downloaded as a tarball** from
  `https://voice-prompts-ipv6.waze.com/<UUID>.tar.gz`. Useful for backing up your
  own pack, and for inspecting how existing packs are built.
- **MP3 files can be uploaded** using the community tooling at
  <https://github.com/pipeeeeees/waze-voicepack-links>, in `mp3_upload/`. The
  advantage over the in-app recorder is that the recorder compresses heavily and
  captures through the phone microphone, whereas an uploaded file arrives intact.
- **There is a hard aggregate size limit** of roughly 0.8 MB across all MP3s in
  a pack.

## The size limit is the thing that will catch you

It is aggregate, not per-file, and Waze enforces it server-side without an error
message. Two symptoms:

- The share button greys out immediately after saving.
- The link works, the pack downloads, and every prompt plays silence, or plays
  the placeholder audio from whatever pack you started from.

This SDK sizes the pack for you and prints the total against the budget before
you upload, so neither symptom should be your first warning. If
`UPLOAD_CHECKLIST.md` says the pack is over budget, fix that before uploading.

Ways to claw back space, roughly in order of what costs you least:

1. Trim silence and dead air from the longest clips. The drive-start greetings
   are usually the worst offenders.
2. Drop `TickerPoints.mp3`, the reroute chime. It is the most omittable file in
   the pack.
3. Drop the roundabout ordinals you will never hear, `Fifth` through `Seventh`.
4. Export a single unit system with `--units metric` or `--units imperial`.
5. Lower `export.max_kbps` in `config/pipeline.json`.

## Uploading

```
python scripts/wvs.py export
```

Then follow the community tool's instructions, pointing it at the `pack/`
directory this step produced. The filenames are already exactly what Waze
expects, and the files are already inside the size budget.

You will get a UUID back. Keep it: it is the only handle on the pack.

## Verify on a real device

Uploading successfully is not the same as the pack working. Confirm:

1. Open the share link on the phone. Waze should offer to add the voice.
2. Select it under `Settings > Voice and sound`.
3. Start a route and listen for a distance callout chained onto a maneuver.
   That single prompt exercises the two file sets most likely to be wrong.
4. If your phone is set to metric, confirm a metric route; if imperial, an
   imperial one. A pack missing one set is silent about it.

If something is wrong, `docs/waze-import-spike.md` is where findings go.

## The in-app recorder still exists

If you would rather not use third-party tooling, the recorder works:
`Settings > Voice and sound > Waze voice > Add a voice`. `scripts/record_assist.py`
walks the prompt list and plays each clip on a keypress so you can record them
into the microphone. Expect worse audio than uploading, because the recorder
compresses what it captures.
"""


def _readme(result: ExportResult, config: PipelineConfig) -> str:
    plan = result.plan
    assert plan is not None
    return f"""# Voice pack export

Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by waze-voice-sdk.

## Contents

- `{PACK_DIRNAME}/` - {len(result.files)} MP3(s), named exactly as Waze expects. This is
  the directory you upload.
- `{CHECKLIST_NAME}` - size report and per-file breakdown.
- `{GUIDE_NAME}` - **read first**: how packs actually get onto a phone.
- `{MANIFEST_NAME}` - machine-readable pack description.

## Size

{_fmt_kb(result.total_bytes)} of {_fmt_kb(plan.budget_bytes)} budget
({plan.utilisation * 100:.1f}%), allocated with the `{plan.strategy}` strategy.

## Rights

This folder may contain audio derived from your source media and voices
synthesized from it. Whether you may use, upload, or share it is your
responsibility. Uploading publishes it to Waze's servers behind a shareable
link. See `LEGAL.md` in the repository root.
"""


def _pack_manifest(result: ExportResult, config: PipelineConfig) -> dict:
    plan = result.plan
    assert plan is not None
    return {
        "schema_version": 2,
        "generator": "waze-voice-sdk",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "units": result.units,
        "budget": {
            "limit_bytes": plan.budget_bytes,
            "total_bytes": result.total_bytes,
            "headroom_bytes": plan.headroom_bytes,
            "utilisation": round(plan.utilisation, 4),
            "within_budget": not result.over_budget,
            "strategy": plan.strategy,
            "correction_passes": result.corrections,
        },
        "share_link_template": wazepack.SHARE_LINK_TEMPLATE,
        "backup_download_template": wazepack.BACKUP_DOWNLOAD_TEMPLATE,
        "clips": [
            {
                "waze_filename": item.slot.filename,
                "phrase_id": item.phrase.id,
                "label": item.phrase.label,
                "text": item.phrase.speech_text,
                "units": item.slot.units,
                "core": item.slot.core,
                "file": f"{PACK_DIRNAME}/{item.slot.filename}",
                "duration_seconds": round(item.allocation.duration, 3),
                "bitrate_kbps": item.allocation.bitrate_kbps,
                "sample_rate": item.allocation.sample_rate,
                "bytes": item.bytes,
                "weight": item.phrase.weight,
            }
            for item in sorted(
                result.files,
                key=lambda entry: wazepack.FILENAME_ORDER.get(entry.slot.filename, 999),
            )
        ],
        "missing": [
            {
                "waze_filename": phrase.waze_filename,
                "phrase_id": phrase.id,
                "label": phrase.label,
                "core": phrase.required,
            }
            for phrase in [*result.missing_core, *result.missing_optional]
        ],
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    master_dir: Path | None = None,
    export_dir: Path | None = None,
    units: str | None = None,
    strategy: str | None = None,
    allow_missing: bool = False,
) -> ExportResult:
    console.step("Export")

    units = units or config.export.units
    if units not in ("both", wazepack.UNITS_METRIC, wazepack.UNITS_IMPERIAL):
        raise SystemExit(f"--units must be both, metric, or imperial; got {units!r}")

    strategy = strategy or config.export.strategy
    if strategy not in budget_module.STRATEGIES:
        raise SystemExit(
            f"Unknown strategy {strategy!r}. Choose one of: "
            f"{', '.join(budget_module.STRATEGIES)}"
        )

    inventory = phrases_module.load(phrases_path)
    master_dir = master_dir or paths.master_dir()
    export_dir = export_dir or paths.export_dir()

    result = ExportResult(units=units)

    wanted = {slot.filename: slot for slot in _wanted_slots(units)}
    by_waze = {
        phrase.waze_filename: phrase for phrase in inventory if phrase.in_waze_pack
    }

    unmapped = [phrase.id for phrase in inventory if not phrase.in_waze_pack]
    if unmapped:
        console.warn(
            f"{len(unmapped)} phrase(s) have no waze_filename and cannot be part of a "
            f"pack: {', '.join(sorted(unmapped)[:6])}"
            + (" ..." if len(unmapped) > 6 else "")
        )

    _clear(export_dir)
    pack_dir = export_dir / PACK_DIRNAME
    pack_dir.mkdir(parents=True, exist_ok=True)

    # -- gather what actually exists ---------------------------------------
    specs: list[budget_module.ClipSpec] = []
    pending: list[tuple[wazepack.WazeSlot, phrases_module.Phrase, Path]] = []

    for filename, slot in wanted.items():
        phrase = by_waze.get(filename)
        if phrase is None:
            continue
        source = master_dir / phrase.filename
        if not source.is_file():
            (result.missing_core if slot.core else result.missing_optional).append(phrase)
            continue

        try:
            duration = media.duration_seconds(source)
        except media.MediaError as error:
            console.error(f"{phrase.id}: could not probe {source.name} ({error})")
            (result.missing_core if slot.core else result.missing_optional).append(phrase)
            continue

        pending.append((slot, phrase, source))
        specs.append(
            budget_module.ClipSpec(
                filename=filename,
                source=source,
                duration=duration,
                weight=phrase.weight,
            )
        )

    if not specs:
        console.warn("No master clips map to Waze prompts. Run the normalize step first.")
        result.plan = budget_module.AllocationPlan(
            budget_bytes=config.export.budget_bytes, strategy=strategy
        )
        _write_docs(result, config, export_dir)
        return result

    # -- allocate ----------------------------------------------------------
    allocation_budget = max(
        0, config.export.budget_bytes - config.export.overhead_reserve_bytes
    )
    plan = budget_module.allocate(
        specs,
        budget_bytes=allocation_budget,
        strategy=strategy,
        min_kbps=config.export.min_kbps,
        max_kbps=config.export.max_kbps,
        sample_rate_policy=config.export.sample_rate_policy,
    )
    # Measurement and reporting are against the real limit, not the reserved figure.
    plan.budget_bytes = config.export.budget_bytes
    result.plan = plan

    for slot, phrase, source in pending:
        allocation = plan.get(slot.filename)
        if allocation is None:
            continue
        result.files.append(
            PackFile(
                slot=slot,
                phrase=phrase,
                source=source,
                destination=pack_dir / slot.filename,
                allocation=allocation,
            )
        )

    console.detail(
        f"Allocating {_fmt_kb(plan.budget_bytes)} across {len(result.files)} clip(s) "
        f"({plan.total_duration:.1f}s of audio) using the '{strategy}' strategy"
    )

    # -- encode, measure, correct -----------------------------------------
    _encode_all(result.files)
    result.corrections = _correct_overshoot(result.files, plan, config)
    if result.corrections:
        console.detail(
            f"Re-encoded {result.corrections} clip(s) a rung lower to absorb "
            "MP3 container overhead."
        )

    _report(result, plan)
    _write_docs(result, config, export_dir)

    if result.over_budget:
        console.error(
            f"Pack is {_fmt_kb(-plan.headroom_bytes)} over Waze's budget. "
            "Uploading it will be rejected silently."
        )
        console.detail(f"See {GUIDE_NAME} for what to cut.")
    if result.missing_core:
        console.bullets(
            "Missing prompts a pack really wants:",
            [f"{phrase.waze_filename}: {phrase.label}" for phrase in result.missing_core],
        )
        if not allow_missing:
            console.warn("Re-run with --allow-missing to build an incomplete pack anyway.")

    return result


def _report(result: ExportResult, plan: budget_module.AllocationPlan) -> None:
    biggest = plan.in_size_order()[:5]
    rows = [
        (
            item.filename,
            f"{item.duration:.2f}s",
            f"{item.bitrate_kbps}k",
            f"{item.sample_rate // 1000}k",
            _fmt_kb(item.bytes),
        )
        for item in biggest
    ]
    console.info("")
    console.info("Largest files:")
    console.table(rows, headers=("File", "Length", "Rate", "SR", "Size"))

    console.info("")
    verdict = "within budget" if plan.fits else "OVER BUDGET"
    console.info(
        f"Pack total: {_fmt_kb(result.total_bytes)} of {_fmt_kb(plan.budget_bytes)} "
        f"({plan.utilisation * 100:.1f}%) - {verdict}"
    )
    for note in plan.notes:
        console.warn(note)


def _write_docs(result: ExportResult, config: PipelineConfig, export_dir: Path) -> None:
    checklist = export_dir / CHECKLIST_NAME
    checklist.write_text(_checklist(result, config), encoding="utf-8")
    result.checklist = checklist

    guide = export_dir / GUIDE_NAME
    guide.write_text(_guide(), encoding="utf-8")
    result.guide = guide

    pack_manifest = export_dir / MANIFEST_NAME
    pack_manifest.write_text(
        json.dumps(_pack_manifest(result, config), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    result.pack_manifest = pack_manifest

    (export_dir / README_NAME).write_text(_readme(result, config), encoding="utf-8")

    console.detail(f"Pack:      {export_dir / PACK_DIRNAME}")
    console.detail(f"Checklist: {checklist.name}")
    console.detail(f"Read first: {guide.name}")
