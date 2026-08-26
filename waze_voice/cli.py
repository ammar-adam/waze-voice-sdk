"""waze-voice-sdk command line.

One entry point for the whole pipeline:

    python scripts/wvs.py doctor
    python scripts/wvs.py run --sources data/my-sources.csv
    python scripts/wvs.py qa --route highway_merge

The individual step scripts next to this file still work and call the same code.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from . import budget, console, doctor, media, packs, paths, preflight, presets, providers
from . import config as config_module
from .steps import clean, export, extract, normalize, qa, synth, validate

PIPELINE_ORDER = ["extract", "clean", "synth", "normalize", "validate", "export"]


# --------------------------------------------------------------------------
# Argument plumbing
# --------------------------------------------------------------------------


def _common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--pack",
        help=(
            "Which voice pack to work on. Each pack keeps its own source list "
            "and audio under packs/<name>/. Defaults to $WVS_PACK."
        ),
    )
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument("--phrases", type=Path, help="Path to phrases.json.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser


def _add_extract(subparsers) -> None:
    parser = _common(subparsers.add_parser("extract", help="Cut clips from source media."))
    parser.add_argument("--sources", type=Path, help="Source inventory CSV.")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument("--force", action="store_true", help="Re-cut clips that already exist.")
    parser.add_argument("--dry-run", action="store_true")


def _add_clean(subparsers) -> None:
    parser = _common(subparsers.add_parser("clean", help="Isolate the vocal / reduce noise."))
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--mode", choices=clean.MODES)
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument("--force", action="store_true")


def _add_synth(subparsers) -> None:
    parser = _common(subparsers.add_parser("synth", help="Synthesize phrases missing from source."))
    parser.add_argument("--backend", choices=synth.BACKENDS)
    parser.add_argument(
        "--model",
        choices=synth.CHATTERBOX_MODELS,
        help="Chatterbox variant. nano is the fastest on CPU; turbo is the default.",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--voice",
        help="Voice id for a hosted backend. See: wvs voices --provider <name>",
    )
    parser.add_argument("--provider-model", help="Override the provider's default model.")
    parser.add_argument(
        "--reference",
        type=Path,
        help="Speaker reference WAV. Local backends only; built automatically if omitted.",
    )
    parser.add_argument(
        "--model-path", type=Path, help="Checkpoint directory for the 'finetuned' backend."
    )
    parser.add_argument(
        "--model-config", type=Path, help="config.json for the 'finetuned' backend."
    )
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument(
        "--include-optional", action="store_true", help="Also fill optional phrases."
    )
    parser.add_argument(
        "--accept-voice-terms",
        action="store_true",
        help="Acknowledge that you have the rights and consent to clone this voice.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List gaps without loading a model.")


def _add_normalize(subparsers) -> None:
    parser = _common(
        subparsers.add_parser("normalize", help="Loudness-normalize into audio/master.")
    )
    parser.add_argument(
        "--sources", type=Path, help="Source CSV, read for take preferences."
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--only", nargs="+", metavar="PHRASE_ID")
    parser.add_argument("--lufs", type=float, help="Override the loudness target.")
    parser.add_argument("--force", action="store_true")


def _add_qa(subparsers) -> None:
    parser = _common(subparsers.add_parser("qa", help="Audition the pack as a route."))
    parser.add_argument("--routes", type=Path)
    parser.add_argument(
        "--route", dest="route_id", help="Route id. Defaults to the first route."
    )
    parser.add_argument("--master-dir", type=Path)
    parser.add_argument(
        "--render",
        type=Path,
        metavar="OUT.wav",
        help="Render the route to a file instead of playing it.",
    )
    parser.add_argument(
        "--bed", type=Path, help="Background bed to mix under a render, e.g. road noise."
    )
    parser.add_argument("--bed-db", type=float, default=-20.0)
    parser.add_argument(
        "--auto", action="store_true", help="Play straight through without prompting."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the sequence only.")
    parser.add_argument("--list-routes", action="store_true")


def _add_export(subparsers) -> None:
    parser = _common(subparsers.add_parser("export", help="Build an uploadable Waze pack."))
    parser.add_argument("--master-dir", type=Path)
    parser.add_argument("--export-dir", type=Path)
    parser.add_argument(
        "--units",
        choices=("both", "metric", "imperial"),
        help="Which distance callout set to include. Dropping one frees budget.",
    )
    parser.add_argument(
        "--strategy",
        choices=budget.STRATEGIES,
        help="Bitrate allocation. weighted spends more on short, important clips.",
    )
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an export directory containing unrecognised files.",
    )


def _add_validate(subparsers) -> None:
    parser = _common(subparsers.add_parser("validate", help="Check inventory, coverage, audio."))
    parser.add_argument("--master-dir", type=Path)
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--no-audio-check", action="store_true")


def _add_run(subparsers) -> None:
    parser = _common(subparsers.add_parser("run", help="Run the full pipeline end to end."))
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--clean-mode", choices=clean.MODES)
    parser.add_argument("--from", dest="from_step", choices=PIPELINE_ORDER)
    parser.add_argument("--to", dest="to_step", choices=PIPELINE_ORDER)
    parser.add_argument("--skip", nargs="+", choices=PIPELINE_ORDER, default=[])
    parser.add_argument("--no-tts", action="store_true", help="Do not attempt synthesis.")
    parser.add_argument("--backend", choices=synth.BACKENDS, help="Synthesis backend.")
    parser.add_argument("--voice", help="Voice id for a hosted synthesis backend.")
    parser.add_argument("--preset", help="Character preset. See: wvs presets list")
    parser.add_argument(
        "--accept-voice-terms",
        action="store_true",
        help="Acknowledge voice cloning rights and consent, so synthesis is not skipped.",
    )
    parser.add_argument("--force", action="store_true", help="Redo work that already has output.")
    parser.add_argument("--allow-missing", action="store_true", help="Export even with gaps.")
    parser.add_argument(
        "--units",
        choices=("both", "metric", "imperial"),
        help="Which distance callout set to include in the pack.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wvs",
        description="Build a custom navigation voice pack from your own audio.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _common(subparsers.add_parser("doctor", help="Check the environment."))
    _add_extract(subparsers)
    _add_clean(subparsers)
    _add_synth(subparsers)
    _add_normalize(subparsers)
    _add_qa(subparsers)
    _add_export(subparsers)
    _add_validate(subparsers)
    _add_run(subparsers)

    dataset = _common(
        subparsers.add_parser("dataset", help="Build an LJSpeech dataset for fine-tuning.")
    )
    dataset.add_argument("--source-dir", type=Path)
    dataset.add_argument("--output-dir", type=Path)

    _add_pack(subparsers)
    _add_voices(subparsers)
    _add_quickstart(subparsers)
    _add_presets(subparsers)

    parser_preflight = _common(
        subparsers.add_parser(
            "preflight",
            help="Check everything checkable before spending an API call.",
        )
    )
    parser_preflight.add_argument("--preset", help="Check just this preset.")

    return parser


def _add_presets(subparsers) -> None:
    parser = subparsers.add_parser(
        "presets", help="Character presets: a voice, a direction, and 43 lines."
    )
    actions = parser.add_subparsers(dest="presets_command", required=True)

    listing = actions.add_parser("list", help="Show every preset.")
    listing.add_argument("--quiet", action="store_true")

    show = actions.add_parser("show", help="One preset in full, including its rights.")
    show.add_argument("name")
    show.add_argument("--lines", action="store_true", help="Print all 43 lines.")
    show.add_argument("--quiet", action="store_true")

    checker = actions.add_parser(
        "check", help="Validate a preset the way CI does. Use before opening a PR."
    )
    checker.add_argument("name", nargs="?", help="Omit to check every preset.")
    checker.add_argument("--quiet", action="store_true")


def _add_voices(subparsers) -> None:
    parser = _common(
        subparsers.add_parser("voices", help="List voices a hosted provider offers.")
    )
    parser.add_argument(
        "--provider",
        choices=providers.NAMES,
        help="Defaults to whichever provider has an API key set.",
    )
    parser.add_argument("--search", help="Filter by name or description.")


def _add_quickstart(subparsers) -> None:
    parser = _common(
        subparsers.add_parser(
            "quickstart",
            help="Build a complete pack from a hosted voice, with no source media.",
        )
    )
    parser.add_argument(
        "--provider",
        choices=providers.NAMES,
        help="Defaults to whichever provider has an API key set.",
    )
    parser.add_argument(
        "--preset",
        help=(
            "Character preset: voice, delivery direction, and all 43 prompts "
            "rewritten in character. See: wvs presets list"
        ),
    )
    parser.add_argument("--voice", help="Voice id. Overrides the preset's voice.")
    parser.add_argument("--provider-model", help="Override the provider's default model.")
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Generate the optional prompts too (alerts, roundabout ordinals).",
    )
    parser.add_argument(
        "--units",
        choices=("both", "metric", "imperial"),
        help="Which distance callout set to include.",
    )
    parser.add_argument(
        "--accept-voice-terms",
        action="store_true",
        help="Acknowledge that you have the rights to the voice you selected.",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate everything.")


def _add_pack(subparsers) -> None:
    parser = subparsers.add_parser(
        "pack", help="Manage voice packs (one per voice) in this clone."
    )
    actions = parser.add_subparsers(dest="pack_command", required=True)

    listing = actions.add_parser("list", help="Show every pack and its progress.")
    listing.add_argument("--quiet", action="store_true")

    new = actions.add_parser("new", help="Create a pack.")
    new.add_argument("name", help="Directory-safe name, e.g. narrator-voice.")
    new.add_argument("--label", default="", help="Human-readable name.")
    new.add_argument(
        "--voice",
        default="",
        help="Where the voice comes from. Recorded here for your own reference.",
    )
    new.add_argument("--notes", default="", help="Anything worth remembering.")
    new.add_argument(
        "--copy-phrases",
        action="store_true",
        help="Give this pack its own phrases.json instead of sharing the default.",
    )
    new.add_argument(
        "--copy-routes",
        action="store_true",
        help="Give this pack its own routes.json.",
    )
    new.add_argument("--quiet", action="store_true")

    show = actions.add_parser("show", help="Show one pack in detail.")
    show.add_argument("name")
    show.add_argument("--quiet", action="store_true")


def _load_config(args: argparse.Namespace) -> config_module.PipelineConfig:
    """Load config/pipeline.json, then apply any per-run flag overrides."""
    cfg = config_module.load(getattr(args, "config", None))

    lufs = getattr(args, "lufs", None)
    if lufs is not None:
        cfg = replace(cfg, loudness=replace(cfg.loudness, target_lufs=lufs))

    model = getattr(args, "model", None)
    if model is not None:
        cfg = replace(cfg, synth=replace(cfg.synth, model=model))

    voice = getattr(args, "voice", None)
    if voice:
        cfg = replace(cfg, synth=replace(cfg.synth, voice=voice))

    provider_model = getattr(args, "provider_model", None)
    if provider_model:
        cfg = replace(cfg, synth=replace(cfg.synth, provider_model=provider_model))

    backend = getattr(args, "backend", None)
    if backend:
        cfg = replace(cfg, synth=replace(cfg.synth, backend=backend))

    return cfg


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_extract(args, cfg) -> int:
    result = extract.run(
        config=cfg,
        sources_path=args.sources,
        phrases_path=args.phrases,
        output_dir=args.output_dir,
        only=args.only,
        force=args.force,
        dry_run=args.dry_run,
    )
    return 0 if result.ok else 1


def cmd_clean(args, cfg) -> int:
    result = clean.run(
        config=cfg,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        only=args.only,
        force=args.force,
    )
    return 0 if result.ok else 1


def cmd_synth(args, cfg) -> int:
    result = synth.run(
        config=cfg,
        phrases_path=args.phrases,
        output_dir=args.output_dir,
        backend=args.backend,
        reference=args.reference,
        model_path=args.model_path,
        model_config_path=args.model_config,
        only=args.only,
        include_optional=args.include_optional,
        accept_voice_terms=args.accept_voice_terms,
        force=args.force,
        dry_run=args.dry_run,
    )
    return 0 if result.ok else 1


def cmd_normalize(args, cfg) -> int:
    result = normalize.run(
        config=cfg,
        phrases_path=args.phrases,
        sources_path=args.sources,
        output_dir=args.output_dir,
        only=args.only,
        force=args.force,
    )
    return 0 if result.ok else 1


def cmd_qa(args, cfg) -> int:
    if args.list_routes:
        from . import routes as routes_module

        book = routes_module.load(args.routes)
        console.bullets(
            "Available routes:",
            [f"{route.id}: {route.label} ({len(route.steps)} steps)" for route in book.routes],
        )
        return 0

    result = qa.run(
        config=cfg,
        phrases_path=args.phrases,
        routes_path=args.routes,
        route_id=args.route_id,
        master_dir=args.master_dir,
        render_to=args.render,
        bed=args.bed,
        bed_gain_db=args.bed_db,
        interactive=not args.auto,
        dry_run=args.dry_run,
    )
    return 0 if result.ok else 1


def cmd_export(args, cfg) -> int:
    result = export.run(
        config=cfg,
        phrases_path=args.phrases,
        master_dir=args.master_dir,
        export_dir=args.export_dir,
        units=args.units,
        strategy=args.strategy,
        allow_missing=args.allow_missing,
        force=args.force,
    )
    # Being over budget is never acceptable: the upload would be rejected
    # silently. --allow-missing forgives gaps, not an oversized pack.
    if result.over_budget:
        return 1
    return 0 if (result.ok or args.allow_missing) else 1


def cmd_validate(args, cfg) -> int:
    result = validate.run(
        config=cfg,
        phrases_path=args.phrases,
        master_dir=args.master_dir,
        sources_path=args.sources,
        check_audio=not args.no_audio_check,
    )
    if result.ok:
        return 0
    return 0 if args.allow_missing and not result.property_problems else 1


def cmd_dataset(args, cfg) -> int:
    synth.prepare_dataset(
        phrases_path=args.phrases,
        source_dir=args.source_dir,
        destination=args.output_dir,
    )
    return 0


def cmd_run(args, cfg) -> int:
    """Run the pipeline end to end, reporting a summary of what each step did."""
    steps = list(PIPELINE_ORDER)
    if args.from_step:
        steps = steps[steps.index(args.from_step) :]
    if args.to_step and args.to_step in steps:
        steps = steps[: steps.index(args.to_step) + 1]
    for skipped in args.skip:
        if skipped in steps:
            steps.remove(skipped)
    if args.no_tts and "synth" in steps:
        steps.remove("synth")

    paths.ensure_dirs()
    console.info(f"Pipeline: {' -> '.join(steps)}")

    summary: list[tuple[str, str, str]] = []
    failed = False

    if "extract" in steps:
        extract_result = extract.run(
            config=cfg,
            sources_path=args.sources,
            phrases_path=args.phrases,
            force=args.force,
        )
        summary.append(
            (
                "extract",
                "ok" if extract_result.ok else "failed",
                f"{len(extract_result.extracted)} cut",
            )
        )
        failed = failed or not extract_result.ok

    if "clean" in steps:
        clean_result = clean.run(
            config=cfg,
            mode=args.clean_mode,
            force=args.force,
        )
        summary.append(
            (
                "clean",
                "ok" if clean_result.ok else "failed",
                f"{len(clean_result.cleaned)} cleaned [{clean_result.mode}]",
            )
        )
        failed = failed or not clean_result.ok

    if "synth" in steps:
        available, reason = synth.is_available(args.backend or cfg.synth.backend)
        if not available:
            console.step("Synthesize")
            console.warn(f"Skipping synthesis: {reason}")
            console.detail(
                "Any phrase without source audio will be listed in the export "
                "checklist for manual recording instead. See docs/tts.md."
            )
            summary.append(("synth", "skipped", reason))
        else:
            try:
                synth_result = synth.run(
                    config=cfg,
                    phrases_path=args.phrases,
                    backend=args.backend,
                    accept_voice_terms=args.accept_voice_terms,
                    force=args.force,
                )
                summary.append(
                    (
                        "synth",
                        "ok" if synth_result.ok else "failed",
                        f"{len(synth_result.synthesized)} generated",
                    )
                )
                failed = failed or not synth_result.ok
            except SystemExit as error:
                # Synthesis is optional. A missing model or an unacknowledged
                # consent gate should not throw away the rest of the run.
                console.warn(f"Synthesis stopped: {error}")
                summary.append(("synth", "skipped", "see message above"))

    if "normalize" in steps:
        normalize_result = normalize.run(
            config=cfg,
            phrases_path=args.phrases,
            sources_path=args.sources,
            force=args.force,
        )
        summary.append(
            (
                "normalize",
                "ok" if normalize_result.ok else "incomplete",
                f"{len(normalize_result.normalized)} normalized, "
                f"{len(normalize_result.missing_required)} missing",
            )
        )

    if "validate" in steps:
        validate_result = validate.run(
            config=cfg, phrases_path=args.phrases, sources_path=args.sources
        )
        summary.append(
            (
                "validate",
                "ok" if validate_result.ok else "issues",
                f"{len(validate_result.present)} present, "
                f"{len(validate_result.missing_required)} missing",
            )
        )

    if "export" in steps:
        export_result = export.run(
            config=cfg,
            phrases_path=args.phrases,
            units=getattr(args, "units", None),
            allow_missing=args.allow_missing,
        )
        size = f"{export_result.total_bytes / 1000:.0f} kB"
        summary.append(
            (
                "export",
                "over budget"
                if export_result.over_budget
                else ("ok" if export_result.ok else "incomplete"),
                f"{len(export_result.files)} file(s), {size}",
            )
        )
        failed = failed or export_result.over_budget

    console.step("Summary")
    console.table(summary, headers=("Step", "Result", "Detail"))

    console.info("")
    console.info("Next:")
    console.info("  1. python scripts/wvs.py qa          audition the pack as a route")
    console.info("  2. audio/export/HOW-TO-UPLOAD.md     how packs get onto a phone")
    console.info("  3. audio/export/UPLOAD_CHECKLIST.md  size report and file list")

    return 1 if failed else 0


def _default_provider(requested: str | None) -> str:
    """Pick the provider to use, when the user did not say."""
    if requested:
        return requested

    ready = providers.available()
    if len(ready) == 1:
        return ready[0]
    if not ready:
        lines = [
            f"  {name}: set ${providers.get(name).env_var}"
            f"  ({providers.get(name).signup_url})"
            for name in providers.NAMES
        ]
        raise SystemExit("No hosted provider has an API key set.\n" + "\n".join(lines))
    raise SystemExit(
        f"Several providers have keys set ({', '.join(ready)}). Pick one with --provider."
    )


def cmd_voices(args, cfg) -> int:
    name = _default_provider(args.provider)
    provider_cls = providers.get(name)

    console.step(f"Voices: {name}")
    try:
        # A provider with a fixed catalogue needs neither a key nor a round trip.
        if provider_cls.supports_voice_listing:
            provider = provider_cls.from_env()
        else:
            provider = provider_cls("")
        voices = provider.list_voices()
    except providers.ProviderError as error:
        raise SystemExit(str(error)) from None

    needle = (args.search or "").lower()
    if needle:
        voices = [v for v in voices if needle in v.name.lower() or needle in v.summary.lower()]

    if not voices:
        console.info("No voices matched.")
        return 0

    console.table(
        [(v.id, v.name, v.summary[:56]) for v in voices],
        headers=("Id", "Name", "Notes"),
    )
    console.info("")
    console.info(f"  python scripts/wvs.py quickstart --provider {name} --voice <id>")
    return 0


def cmd_quickstart(args, cfg) -> int:
    """A finished pack from a voice id, with no source media at all.

    This is the shortest path that exists: pick a voice, wait a minute, upload.
    Everything the longer pipeline does for recorded audio (cutting, cleaning,
    take selection) has nothing to do because the audio is generated to spec.
    """
    preset = presets.load(args.preset) if args.preset else None

    # A preset names the provider it was written for; an explicit --provider
    # still wins, since the same lines work anywhere.
    name = _default_provider(args.provider or (preset.provider if preset else None))
    cfg = replace(cfg, synth=replace(cfg.synth, backend=name))

    if preset is not None and not cfg.synth.voice:
        cfg = replace(cfg, synth=replace(cfg.synth, voice=preset.voice))

    if not cfg.synth.voice:
        raise SystemExit(
            "Pick a voice or a preset first:\n"
            f"    python scripts/wvs.py presets list\n"
            f"    python scripts/wvs.py voices --provider {name}\n"
            "then pass --preset <name> or --voice <id>."
        )

    available_now, reason = synth.is_available(name)
    if not available_now:
        raise SystemExit(reason)

    console.step("Quickstart")
    console.info(f"Provider: {name}   Voice: {cfg.synth.voice}")
    if preset is not None:
        console.info(f"Preset:   {preset.label} - {preset.rights.attribution}")
        console.detail(preset.description)
    console.detail("Every prompt is generated from text. No recording, no timestamps.")

    synth_result = synth.run(
        config=cfg,
        phrases_path=args.phrases,
        backend=name,
        include_optional=args.include_optional,
        accept_voice_terms=args.accept_voice_terms,
        force=args.force,
        preset=preset,
    )
    if not synth_result.ok:
        console.error("Some prompts could not be generated; stopping before export.")
        return 1

    normalize.run(config=cfg, phrases_path=args.phrases, force=args.force)
    validate.run(config=cfg, phrases_path=args.phrases)
    export_result = export.run(
        config=cfg,
        phrases_path=args.phrases,
        units=args.units,
        allow_missing=True,
        force=args.force,
        preset=preset,
    )

    console.step("Done")
    if export_result.over_budget:
        console.error("Pack is over Waze's size budget. The checklist says what to cut.")
        return 1

    console.info(
        f"{len(export_result.files)} prompt(s), "
        f"{export_result.total_bytes / 1000:.0f} kB of "
        f"{cfg.export.budget_bytes / 1000:.0f} kB budget."
    )
    console.info("")
    console.info("Next:")
    console.info("  1. python scripts/wvs.py qa        hear it as a route")
    console.info("  2. audio/export/HOW-TO-UPLOAD.md   get it onto your phone")
    return 0


def cmd_preflight(args, cfg) -> int:
    report = preflight.run(config=cfg, phrases_path=args.phrases, only=args.preset)
    return 0 if report.ok else 1


def cmd_presets(args, cfg) -> int:
    if args.presets_command == "list":
        return _presets_list()
    if args.presets_command == "show":
        return _presets_show(args.name, show_lines=args.lines)
    return _presets_check(args.name)


def _presets_list() -> int:
    found = presets.list_presets()
    console.step("Presets")
    if not found:
        console.info("No presets found.")
        return 0

    console.table(
        [
            (
                preset.name,
                preset.label,
                f"{preset.provider}/{preset.voice}",
                preset.rights.attribution,
            )
            for preset in found
        ],
        headers=("Name", "Label", "Voice", "Source work"),
    )
    console.info("")
    console.info("  python scripts/wvs.py quickstart --preset <name>")
    return 0


def _presets_show(name: str, *, show_lines: bool) -> int:
    preset = presets.load(name)
    console.step(f"Preset: {preset.label}")
    console.info(preset.description)
    console.info("")
    console.table(
        [
            ("Voice", f"{preset.provider} / {preset.voice}"),
            ("Lines", f"{len(preset.lines)} ({preset.total_chars} characters)"),
            ("Options", str(preset.provider_options or "-")),
        ],
        headers=("Field", "Value"),
    )

    console.info("")
    console.info("Delivery direction")
    console.detail(preset.direction)

    if preset.notes:
        console.info("")
        console.info("Notes")
        console.detail(preset.notes)

    rights = preset.rights
    console.info("")
    console.info(f"Source work: {rights.attribution}")
    console.detail(rights.pd_basis)
    console.bullets("Covered", rights.covered)
    console.bullets("NOT covered", rights.not_covered)

    if show_lines:
        console.info("")
        console.table(
            sorted(preset.lines.items()), headers=("Phrase", "Line")
        )
    return 0


def _presets_check(name: str | None) -> int:
    """What CI runs. A preset that fails this is not shippable."""
    names = [name] if name else sorted(
        path.stem for path in presets.presets_dir().glob("*.json")
    )
    if not names:
        console.warn("No presets to check.")
        return 0

    console.step("Checking presets")
    failed = False
    for preset_name in names:
        errors, warnings = presets.check(preset_name)
        if errors:
            failed = True
            console.error(f"{preset_name}: {len(errors)} problem(s)")
            for error in errors:
                console.detail(error)
        else:
            suffix = f" ({len(warnings)} warning(s))" if warnings else ""
            console.ok(f"{preset_name}{suffix}")
            for warning in warnings:
                console.detail(warning)

    return 1 if failed else 0


def cmd_pack(args, cfg) -> int:
    if args.pack_command == "list":
        return _pack_list()
    if args.pack_command == "new":
        return _pack_new(args)
    return _pack_show(args.name)


def _pack_list() -> int:
    found = packs.list_packs()
    console.step("Packs")
    if not found:
        console.info("No packs yet.")
        console.info("")
        console.info("  python scripts/wvs.py pack new my-voice --label \"My voice\"")
        console.info("")
        console.info(
            "Without a pack the pipeline uses the shared audio/ tree, which is "
            "fine for a single voice."
        )
        return 0

    rows = []
    for pack in found:
        size = pack.pack_bytes()
        rows.append(
            (
                pack.name,
                pack.display_label,
                f"{pack.master_count()} clips",
                f"{size / 1000:.0f} kB" if size else "-",
                "yes" if pack.has_sources else "no",
                ", ".join(pack.overrides) or "-",
            )
        )
    console.table(
        rows, headers=("Name", "Label", "Mastered", "Pack", "Sources", "Overrides")
    )
    console.info("")
    console.info("  python scripts/wvs.py run --pack <name>")
    return 0


def _pack_new(args) -> int:
    pack = packs.create(
        args.name,
        label=args.label,
        voice=args.voice,
        notes=args.notes,
        copy_phrases=args.copy_phrases,
        copy_routes=args.copy_routes,
    )
    console.step(f"Created pack '{pack.name}'")
    console.ok(str(pack.root))
    console.info("")
    console.info("Next:")
    console.info(f"  1. Fill in {pack.sources_path.relative_to(paths.repo_root())}")
    console.info(f"  2. python scripts/wvs.py run --pack {pack.name}")
    console.info("")
    console.detail(
        "This pack falls back to the shared config for anything it does not "
        "override, so the Waze prompt list is already set up."
    )
    return 0


def _pack_show(name: str) -> int:
    pack = packs.load(name)
    console.step(f"Pack '{pack.name}'")
    size = pack.pack_bytes()
    console.table(
        [
            ("Label", pack.display_label),
            ("Voice", pack.voice or "-"),
            ("Notes", pack.notes or "-"),
            ("Created", pack.created_at or "-"),
            ("Root", str(pack.root)),
            ("Source list", str(pack.sources_path) if pack.has_sources else "not created"),
            ("Overrides", ", ".join(pack.overrides) or "none (uses shared config)"),
            ("Mastered clips", str(pack.master_count())),
            ("Exported pack", f"{size / 1000:.1f} kB" if size else "not built"),
        ],
        headers=("Field", "Value"),
    )
    return 0


COMMANDS = {
    "extract": cmd_extract,
    "clean": cmd_clean,
    "synth": cmd_synth,
    "normalize": cmd_normalize,
    "qa": cmd_qa,
    "export": cmd_export,
    "validate": cmd_validate,
    "dataset": cmd_dataset,
    "run": cmd_run,
    "pack": cmd_pack,
    "voices": cmd_voices,
    "quickstart": cmd_quickstart,
    "presets": cmd_presets,
    "preflight": cmd_preflight,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console.set_quiet(getattr(args, "quiet", False))

    # Set before anything resolves a path. Every directory the pipeline touches
    # hangs off this, so choosing the pack late would have half the run reading
    # one tree and half another.
    requested_pack = getattr(args, "pack", None)
    if requested_pack:
        if not packs.exists(requested_pack):
            packs.load(requested_pack)  # raises with the list of packs that do exist
        paths.set_active_pack(requested_pack)

    if args.command == "doctor":
        return doctor.run()

    if args.command == "pack":
        return cmd_pack(args, None)

    cfg = _load_config(args)
    paths.ensure_dirs()

    active = paths.active_pack()
    if active:
        console.detail(f"Pack: {active}")

    try:
        return COMMANDS[args.command](args, cfg)
    except media.MediaError as error:
        # Steps handle per-clip failures themselves. This catches whatever they
        # do not, so an ffmpeg problem reaches the user as a sentence rather
        # than a stack trace ending somewhere in subprocess.
        console.error(str(error))
        return 1
    except ValueError as error:
        # Config that contradicts itself, e.g. a bitrate ceiling below the
        # encoder floor. Raised where the constraint lives, reported here.
        console.error(str(error))
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.info("\nInterrupted.")
        sys.exit(130)
