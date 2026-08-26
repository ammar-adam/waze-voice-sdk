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

from . import budget, console, doctor, paths
from . import config as config_module
from .steps import clean, export, extract, normalize, qa, synth, validate

PIPELINE_ORDER = ["extract", "clean", "synth", "normalize", "validate", "export"]


# --------------------------------------------------------------------------
# Argument plumbing
# --------------------------------------------------------------------------


def _common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
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
        "--reference",
        type=Path,
        help="Speaker reference WAV. Built automatically if omitted.",
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

    return parser


def _load_config(args: argparse.Namespace) -> config_module.PipelineConfig:
    """Load config/pipeline.json, then apply any per-run flag overrides."""
    cfg = config_module.load(getattr(args, "config", None))

    lufs = getattr(args, "lufs", None)
    if lufs is not None:
        cfg = replace(cfg, loudness=replace(cfg.loudness, target_lufs=lufs))

    model = getattr(args, "model", None)
    if model is not None:
        cfg = replace(cfg, synth=replace(cfg.synth, model=model))

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
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console.set_quiet(getattr(args, "quiet", False))

    if args.command == "doctor":
        return doctor.run()

    cfg = _load_config(args)
    paths.ensure_dirs()
    return COMMANDS[args.command](args, cfg)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.info("\nInterrupted.")
        sys.exit(130)
