"""Step 2: isolate the vocal and clean up background music or noise.

Three modes, in increasing order of cost:

``copy``
    Pass clips through untouched. Useful when the source is already clean
    studio dialogue.
``ffmpeg``
    Band-limit plus spectral denoise using ffmpeg alone. No PyTorch, no model
    download, runs in seconds. This is the default because it is the only mode
    guaranteed to work on a machine that already satisfies the base install.
``demucs``
    Full source separation with Demucs, keeping the vocal stem. This is what
    actually rescues a line buried under a score, at the cost of a multi-GB
    PyTorch install.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .. import console, manifest as manifest_module, media, paths, sources
from ..config import PipelineConfig

MODES = ("copy", "ffmpeg", "demucs")

_DEMUCS_INSTALL_HINT = (
    "Install Demucs into the same interpreter you are running:\n"
    "    python -m pip install -U demucs\n"
    "Demucs pulls in PyTorch, which is a large download. To keep going without "
    "it, run with --mode ffmpeg (band-limit plus denoise) or --mode copy."
)


@dataclass
class CleanResult:
    cleaned: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    reverted: list[str] = field(default_factory=list)
    mode: str = "copy"

    @property
    def ok(self) -> bool:
        return not self.failures


def _input_clips(input_dir: Path) -> list[Path]:
    """Extracted clips, sorted for deterministic ordering."""
    return sorted(
        path
        for path in input_dir.glob("*.wav")
        if path.is_file() and not path.name.startswith(".")
    )


def _polish_chain(config: PipelineConfig) -> list[str]:
    """Band-limiting and denoise applied in ffmpeg and demucs modes alike."""
    chain: list[str] = []
    if config.clean.highpass_hz > 0:
        # Rolls off rumble, handling noise, and most residual bass content.
        chain.append(f"highpass=f={config.clean.highpass_hz}")
    if config.clean.lowpass_hz > 0:
        chain.append(f"lowpass=f={config.clean.lowpass_hz}")
    if config.clean.denoise:
        # Spectral noise reduction, kept near ffmpeg's own default. Aggressive
        # settings sound impressive on hiss and then quietly gut a soft line.
        chain.append(f"afftdn=nf={config.clean.denoise_floor_db}")
    return chain


def _guard_against_signal_loss(
    original: Path,
    cleaned: Path,
    config: PipelineConfig,
) -> str:
    """Revert to the unprocessed clip when cleaning destroyed the signal.

    Spectral denoise decides what counts as noise from the clip's own content. A
    quiet or steady delivery can look exactly like the noise it is trying to
    remove, and the filter takes the lot. That failure is silent: the file still
    exists, still has the right duration, and plays back as nothing. Comparing
    loudness before and after catches it.
    """
    kwargs = {
        "target_lufs": config.loudness.target_lufs,
        "true_peak_db": config.loudness.true_peak_db,
        "loudness_range": config.loudness.loudness_range,
        "pad_below_seconds": config.loudness.short_clip_seconds,
    }
    try:
        before = media.measure_loudness(original, **kwargs)
        after = media.measure_loudness(cleaned, **kwargs)
    except media.MediaError:
        return ""  # Not worth failing the step over a measurement problem.

    if before.is_silent:
        return ""  # Nothing there to begin with; normalization will flag it.

    loss = before.integrated_lufs - after.integrated_lufs
    if after.is_silent or loss > config.clean.max_loss_lu:
        shutil.copy2(original, cleaned)
        message = (
            f"cleaning removed {loss:.1f} LU; reverted to the unprocessed clip"
            if not after.is_silent
            else "cleaning left silence; reverted to the unprocessed clip"
        )
        console.warn(f"{original.stem}: {message}")
        return message
    return ""


def demucs_command() -> list[str] | None:
    """Locate Demucs, preferring the console script but accepting the module."""
    binary = media.find_tool("demucs")
    if binary:
        return [binary]

    try:
        import importlib.util

        if importlib.util.find_spec("demucs") is not None:
            return [sys.executable, "-m", "demucs"]
    except (ImportError, ValueError):
        pass
    return None


def _run_demucs(
    clips: Sequence[Path],
    work_dir: Path,
    config: PipelineConfig,
) -> dict[str, Path]:
    """Separate every clip in one Demucs invocation and map stem -> vocals file.

    Demucs writes ``<out>/<model>/<track stem>/vocals.wav`` rather than flat
    files, so the caller cannot simply glob the output directory and keep phrase
    IDs. Passing every clip to a single invocation also matters: Demucs loads its
    model on startup, so a per-file loop pays that cost once per clip.
    """
    command = demucs_command()
    if command is None:
        raise SystemExit(f"Demucs was not found.\n{_DEMUCS_INSTALL_HINT}")

    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    console.detail(
        f"Running Demucs ({config.clean.demucs_model}, {config.clean.demucs_device}) "
        f"on {len(clips)} clip(s). The first run downloads model weights."
    )

    full_command = [
        *command,
        "--two-stems",
        "vocals",
        "-n",
        config.clean.demucs_model,
        "-d",
        config.clean.demucs_device,
        "-o",
        str(work_dir),
        *[str(path) for path in clips],
    ]

    try:
        media.run(full_command, capture=False)
    except media.MediaError as error:
        raise SystemExit(f"Demucs failed.\n{error}\n\n{_DEMUCS_INSTALL_HINT}") from None

    separated: dict[str, Path] = {}
    for vocals in work_dir.rglob("vocals.*"):
        separated[vocals.parent.name] = vocals

    missing = [path.stem for path in clips if path.stem not in separated]
    if missing:
        console.warn(
            "Demucs produced no vocal stem for: " + ", ".join(sorted(missing))
        )
    return separated


def run(
    *,
    config: PipelineConfig,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
    mode: str | None = None,
    only: Iterable[str] | None = None,
    force: bool = False,
) -> CleanResult:
    console.step("Clean")

    mode = mode or config.clean.mode
    if mode not in MODES:
        raise SystemExit(f"Unknown clean mode {mode!r}. Choose one of: {', '.join(MODES)}")

    input_dir = input_dir or paths.extracted_dir()
    output_dir = output_dir or paths.processed_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    clips = _input_clips(input_dir)
    if only:
        wanted = {value.strip() for value in only}
        clips = [
            path
            for path in clips
            if (parsed := sources.parse_stem(path.stem)) is not None and parsed[0] in wanted
        ]

    result = CleanResult(mode=mode)
    if not clips:
        console.warn(f"No clips found in {input_dir}. Run the extract step first.")
        return result

    pending = clips if force else [
        path for path in clips if not (output_dir / f"{path.stem}.wav").is_file()
    ]
    for path in clips:
        if path not in pending:
            console.detail(f"skip (exists) {path.stem}.wav")
            result.skipped.append(output_dir / f"{path.stem}.wav")

    if not pending:
        console.info("Every clip already has a processed version. Use --force to redo them.")
        return result

    separated: dict[str, Path] = {}
    if mode == "demucs":
        separated = _run_demucs(pending, paths.work_dir() / "demucs", config)

    manifest = manifest_module.Manifest.load()
    polish = _polish_chain(config) if mode != "copy" else []

    for path in pending:
        destination = output_dir / f"{path.stem}.wav"
        source_for_polish = path

        if mode == "demucs":
            vocal = separated.get(path.stem)
            if vocal is None:
                console.error(f"{path.stem}: no vocal stem produced; leaving it out.")
                result.failures.append(path.stem)
                continue
            source_for_polish = vocal

        try:
            if mode == "copy":
                shutil.copy2(path, destination)
                note = ""
            else:
                media.render(
                    source_for_polish,
                    destination,
                    filters=polish,
                    sample_rate=config.audio.sample_rate,
                    channels=config.audio.channels,
                )
                note = _guard_against_signal_loss(path, destination, config)
        except (media.MediaError, OSError) as error:
            console.error(f"{path.stem}: {error}")
            result.failures.append(path.stem)
            continue

        parsed = sources.parse_stem(path.stem)
        if parsed is not None:
            phrase_id, take = parsed
            record = manifest.record(phrase_id)
            record.processed_path = str(destination)
            record.clean_mode = mode if not note else f"{mode} (reverted)"
            if record.take is None:
                record.take = take
            if note:
                record.add_warning(note)
            record.mark_stage("clean")

        console.ok(f"{destination.name}  [{mode}]" + (f"  {note}" if note else ""))
        result.cleaned.append(destination)
        if note:
            result.reverted.append(path.stem)

    manifest.save()
    console.info(f"Cleaned {len(result.cleaned)} clip(s) in '{mode}' mode.")
    if result.reverted:
        console.bullets(
            "Reverted to the unprocessed clip (cleaning was destroying the signal):",
            result.reverted,
        )
        console.detail(
            "Lower clean.denoise_floor_db in config/pipeline.json, or use "
            "--mode demucs, if these clips genuinely need cleaning."
        )
    return result
