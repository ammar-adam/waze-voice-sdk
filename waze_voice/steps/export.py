"""Step 6: assemble the export folder and the paperwork that goes with it.

The import path into Waze is not settled. The in-app custom voice recorder is
the one route known to work; whether a pre-rendered clip can be injected
directly has not been verified on a real device. Everything this step writes is
built around that: it produces an ordered clip folder that works for the
recorder workflow today, a machine-readable manifest that a direct-import path
could consume if one turns out to exist, and a verification guide that tells the
user how to find out for themselves before they spend an hour recording.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import (
    console,
    manifest as manifest_module,
    media,
    paths,
    phrases as phrases_module,
)
from ..config import PipelineConfig

CLIPS_DIRNAME = "clips"
CHECKLIST_NAME = "IMPORT_CHECKLIST.md"
VERIFY_NAME = "VERIFY-IMPORT-FIRST.md"
MANIFEST_NAME = "pack-manifest.json"
README_NAME = "README.md"


@dataclass
class ExportedClip:
    index: int
    phrase: phrases_module.Phrase
    path: Path
    duration: float
    origin: str


@dataclass
class ExportResult:
    exported: list[ExportedClip] = field(default_factory=list)
    missing_required: list[phrases_module.Phrase] = field(default_factory=list)
    missing_optional: list[phrases_module.Phrase] = field(default_factory=list)
    checklist: Path | None = None
    verify_guide: Path | None = None
    pack_manifest: Path | None = None

    @property
    def ok(self) -> bool:
        return not self.missing_required


def _clear(export_dir: Path) -> None:
    """Empty the export folder, keeping the .gitkeep that holds it in Git."""
    export_dir.mkdir(parents=True, exist_ok=True)
    for path in export_dir.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink()


def _duration(path: Path) -> float:
    try:
        return media.duration_seconds(path)
    except media.MediaError:
        return 0.0


def _checklist(result: ExportResult, config: PipelineConfig) -> str:
    total = len(result.exported)
    synthetic = [clip for clip in result.exported if clip.origin == manifest_module.ORIGIN_SYNTHESIZED]

    lines = [
        "# Waze Recorder Import Checklist",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        f"{total} clip(s) ready, normalized to {config.loudness.target_lufs} LUFS "
        f"with a {config.loudness.true_peak_db} dBTP ceiling.",
        "",
        "> Before working through this list, read VERIFY-IMPORT-FIRST.md and run the",
        "> five-minute check it describes. It tells you whether you need to record",
        "> every prompt by hand or whether your device offers a faster path. Doing",
        "> that check first can save you the entire session below.",
        "",
        "## Recorder workflow",
        "",
        "1. Open Waze on your phone.",
        "2. Go to `Settings > Voice and sound > Waze voice > Add a voice`.",
        "3. Waze prompts you for each phrase in its own fixed order. Find the",
        "   matching row below by its wording, not by the number in this file:",
        "   the numbering here is this pack's order, and Waze may ask in a",
        "   different one.",
        "4. Play the exported clip into the phone microphone, or record the line",
        "   yourself, then confirm Waze accepted it.",
        "5. Tick the box and move on.",
        "",
        "`python scripts/record_assist.py` walks this list one prompt at a time and",
        "plays each clip on a keypress, which is easier than juggling a file browser",
        "while holding a phone.",
        "",
        "## Prompts",
        "",
        "| # | Done | Phrase | Say | Clip | Length | Source |",
        "| - | ---- | ------ | --- | ---- | ------ | ------ |",
    ]

    for clip in result.exported:
        origin = {
            manifest_module.ORIGIN_SYNTHESIZED: "synthesized",
            manifest_module.ORIGIN_EXTRACTED: "source media",
            manifest_module.ORIGIN_MANUAL: "manual",
        }.get(clip.origin, clip.origin or "unknown")
        required = "required" if clip.phrase.required else "optional"
        lines.append(
            f"| {clip.index:03d} | [ ] | {clip.phrase.label} ({required}) | "
            f"\"{clip.phrase.speech_text}\" | `{clip.path.name}` | "
            f"{clip.duration:.2f}s | {origin} |"
        )

    if result.missing_required or result.missing_optional:
        lines += ["", "## Not in this pack", ""]
        for phrase in result.missing_required:
            lines.append(
                f"- [ ] **{phrase.label}** (required) - no clip. Record this one "
                "directly in Waze, or add a source row and re-run the pipeline."
            )
        for phrase in result.missing_optional:
            lines.append(f"- [ ] {phrase.label} (optional) - no clip.")

    if synthetic:
        lines += [
            "",
            "## Synthesized prompts",
            "",
            "These were not in your source media and were generated to match your",
            "voice. Listen to each one before recording it: synthetic lines drift in",
            "pace and emphasis more than cut audio does.",
            "",
        ]
        for clip in synthetic:
            lines.append(f"- {clip.phrase.label} (`{clip.path.name}`)")

    lines.append("")
    return "\n".join(lines)


def _verify_guide() -> str:
    return """# Verify the import path before you record anything

## What is actually known

Waze's in-app custom voice recorder is the one documented, public way to get a
custom voice onto a device. It records prompts through the phone microphone.

Whether a **pre-rendered audio file** can be injected directly, skipping the
microphone, is **not verified**. This SDK does not claim it can. Nothing in this
export folder depends on it working.

Anything you read online asserting a ZIP or manifest import format for Waze
custom voices should be treated as unconfirmed until you have reproduced it on
your own device and Waze version. App behaviour changes between releases, and it
differs between Android and iOS.

## Run this check first (about five minutes)

Do this before working through the full checklist. It costs one prompt and tells
you which of the three outcomes below you are in.

1. Install the current Waze release on the device you will navigate with.
2. Note the exact app version: `Settings > About > Waze version`. Write it down;
   a result without a version number is not reproducible.
3. Go to `Settings > Voice and sound > Waze voice > Add a voice`.
4. Record a single prompt normally, in your own voice. Confirm it saves.
5. Now try to reach the stored recording:
   - **Android:** look for a Waze media or voices directory under
     `Android/media/com.waze/` using the system Files app. Content under
     `Android/media/` is readable without root; `Android/data/` generally is not
     on Android 11 and later. If you find the recording, try replacing it with
     the matching clip from `clips/`, keeping the original filename, format, and
     sample rate.
   - **iOS:** the app container is not user-accessible without a full device
     backup round trip. Assume the recorder is the only path.
6. Start a route and drive or simulate it until the prompt fires.

## The three outcomes

**A. Direct replacement works.** The clip you dropped in plays during
navigation. Record what you did in `docs/waze-import-spike.md`, including the
exact path and filename convention, and open an issue. `pack-manifest.json` in
this folder already carries the metadata a direct-import script would need.

**B. Only the recorder works.** Expected. Work through `IMPORT_CHECKLIST.md`
using the recorder, playing each exported clip into the microphone.

**C. Something else entirely.** The menu path moved, the feature is gone in your
region, or the recorder behaves differently. Write down what you actually saw in
`docs/waze-import-spike.md` before adapting.

## Playing clips into the microphone

If you land in outcome B, the recording quality of that mic pass now dominates
everything the pipeline did. Worth getting right:

- Quiet room. The recorder captures whatever else is happening.
- Hold the phone 15-30 cm from the speaker. Closer distorts, further picks up
  the room.
- Set playback volume so the loudest prompt does not distort, then leave it
  alone. Changing volume mid-session undoes the loudness normalization.
- Do a single test prompt and play it back inside Waze before doing all of them.
- The clips already carry ~60 ms of lead-in silence so the recorder does not
  clip the first syllable. Start playback promptly once recording begins.

## Report back

Whatever happens, fill in `docs/waze-import-spike.md`: device, OS version, Waze
version, date, steps, and result. The uncertainty in this file only shrinks when
someone writes down what they saw.
"""


def _readme(result: ExportResult, config: PipelineConfig) -> str:
    return f"""# Voice pack export

Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by waze-voice-sdk.

## Contents

- `{CLIPS_DIRNAME}/` - {len(result.exported)} normalized clip(s), numbered in pack order.
- `{CHECKLIST_NAME}` - the prompt-by-prompt recording checklist.
- `{VERIFY_NAME}` - **read this first**; how to find out which import path your device supports.
- `{MANIFEST_NAME}` - machine-readable pack description.

## Audio format

- {config.audio.master_format.upper()}, mono, {config.audio.sample_rate} Hz, {config.audio.master_bitrate}
- {config.loudness.target_lufs} LUFS integrated, {config.loudness.true_peak_db} dBTP ceiling
- Leading silence {config.trim.lead_in_ms} ms, trailing {config.trim.lead_out_ms} ms

## Rights

This folder may contain audio derived from your source media and voices
synthesized from it. Whether you may use or distribute it is your
responsibility. See `LEGAL.md` in the repository root.
"""


def _pack_manifest(
    result: ExportResult,
    config: PipelineConfig,
    build: manifest_module.Manifest,
) -> dict:
    """A description of the pack that a future direct-import path could consume.

    The format is this SDK's own, not Waze's. No public Waze pack format is
    confirmed to exist; this exists so that if one is discovered, the metadata
    needed to build it has already been captured.
    """
    return {
        "schema_version": 1,
        "generator": "waze-voice-sdk",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "import_path_verified": False,
        "import_note": (
            "The in-app recorder is the only confirmed import path. Direct clip "
            "injection is unverified. See VERIFY-IMPORT-FIRST.md."
        ),
        "audio": {
            "format": config.audio.master_format,
            "channels": config.audio.channels,
            "sample_rate": config.audio.sample_rate,
            "bitrate": config.audio.master_bitrate,
            "target_lufs": config.loudness.target_lufs,
            "true_peak_db": config.loudness.true_peak_db,
        },
        "clips": [
            {
                "index": clip.index,
                "phrase_id": clip.phrase.id,
                "label": clip.phrase.label,
                "text": clip.phrase.speech_text,
                "group": clip.phrase.group,
                "required": clip.phrase.required,
                "file": f"{CLIPS_DIRNAME}/{clip.path.name}",
                "duration_seconds": round(clip.duration, 3),
                "origin": clip.origin,
                "output_lufs": (
                    build.get(clip.phrase.id).output_lufs if build.get(clip.phrase.id) else None
                ),
            }
            for clip in result.exported
        ],
        "missing": [
            {"phrase_id": phrase.id, "label": phrase.label, "required": phrase.required}
            for phrase in [*result.missing_required, *result.missing_optional]
        ],
    }


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    master_dir: Path | None = None,
    export_dir: Path | None = None,
    allow_missing: bool = False,
) -> ExportResult:
    console.step("Export")

    inventory = phrases_module.load(phrases_path)
    master_dir = master_dir or paths.master_dir()
    export_dir = export_dir or paths.export_dir()
    build = manifest_module.Manifest.load()

    _clear(export_dir)
    clips_dir = export_dir / CLIPS_DIRNAME
    clips_dir.mkdir(parents=True, exist_ok=True)

    result = ExportResult()
    index = 0

    for phrase in inventory.in_export_order():
        source = master_dir / phrase.filename
        if not source.is_file():
            if phrase.required:
                result.missing_required.append(phrase)
            else:
                result.missing_optional.append(phrase)
            continue

        # Only clips that actually exist consume a number, so the checklist has
        # no gaps to explain.
        index += 1
        destination = clips_dir / f"{index:03d}_{phrase.id}{source.suffix}"
        shutil.copy2(source, destination)

        record = build.get(phrase.id)
        result.exported.append(
            ExportedClip(
                index=index,
                phrase=phrase,
                path=destination,
                duration=_duration(destination),
                origin=record.origin if record else "",
            )
        )
        console.ok(f"{destination.name}")

    checklist = export_dir / CHECKLIST_NAME
    checklist.write_text(_checklist(result, config), encoding="utf-8")
    result.checklist = checklist

    verify = export_dir / VERIFY_NAME
    verify.write_text(_verify_guide(), encoding="utf-8")
    result.verify_guide = verify

    pack = export_dir / MANIFEST_NAME
    pack.write_text(
        json.dumps(_pack_manifest(result, config, build), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    result.pack_manifest = pack

    (export_dir / README_NAME).write_text(_readme(result, config), encoding="utf-8")

    console.info(f"Exported {len(result.exported)} clip(s) to {export_dir}")
    console.detail(f"Checklist:      {checklist.name}")
    console.detail(f"Read first:     {verify.name}")
    console.detail(f"Pack manifest:  {pack.name}")

    if result.missing_required:
        console.bullets(
            "Missing required clips (the checklist marks these for manual recording):",
            [f"{phrase.id}: {phrase.filename}" for phrase in result.missing_required],
        )
        if not allow_missing:
            console.warn("Re-run with --allow-missing to export an incomplete pack anyway.")

    return result
