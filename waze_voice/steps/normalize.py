"""Step 4: loudness-normalize every clip to one consistent level.

The approach is measure-then-apply rather than ffmpeg's single-pass ``loudnorm``.
Single-pass loudnorm runs in dynamic mode: it compresses to hit the target as it
goes, which pumps on short material and gives a different result depending on
where the speech falls in the clip. Measuring first and applying one static gain
is transparent, reproducible, and preserves the delivery of the original take.

Short clips get special handling. See :func:`waze_voice.media.measure_loudness`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .. import (
    console,
    manifest as manifest_module,
    media,
    paths,
    phrases as phrases_module,
    sources as sources_module,
    takes,
)
from ..config import PipelineConfig

# Residual error worth a second render. Well inside audibility, but tight enough
# that every clip in a pack lands on the same level.
_CORRECTION_THRESHOLD_LU = 0.3


@dataclass
class NormalizedClip:
    phrase_id: str
    path: Path
    input_lufs: float
    output_lufs: float
    output_true_peak_db: float
    gain_db: float
    origin: str

    @property
    def deviation(self) -> float:
        return self.output_lufs


@dataclass
class NormalizeResult:
    normalized: list[NormalizedClip] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    outliers: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures and not self.missing_required


def _preferred_takes(sources_path: Path | None) -> dict[str, int]:
    """Read take preferences from the source CSV when one is available.

    Normalization runs happily without a source CSV (for example on a pack built
    entirely from TTS), so a missing or unreadable file is not fatal here.
    """
    if sources_path is None or not sources_path.is_file():
        return {}
    try:
        clips = sources_module.load(sources_path)
    except SystemExit:
        console.warn(
            f"Could not read take preferences from {sources_path.name}; "
            "falling back to the lowest-numbered take."
        )
        return {}

    result: dict[str, int] = {}
    for phrase_id in {clip.phrase_id for clip in clips}:
        take = sources_module.preferred_take(clips, phrase_id)
        if take is not None:
            result[phrase_id] = take
    return result


def _trim_chain(config: PipelineConfig) -> list[str]:
    """Strip leading and trailing silence.

    Run on its own, before anything time-based. Trimming changes the clip's
    length, so a fade positioned against the pre-trim duration would land in the
    wrong place, or past the end and not happen at all.
    """
    if not config.trim.enabled:
        return []
    return media.trim_silence_chain(config.trim.threshold_db)


def _shape_chain(config: PipelineConfig, trimmed_duration: float) -> list[str]:
    """Fade the trimmed edges and restore controlled padding.

    Deliberately does not touch the level. Loudness is measured *after* this,
    so the measurement is taken on audio shaped exactly like the file that
    ships. Measuring before shaping leaves the padding and fades to shift the
    result afterwards, which on a sub-second prompt is worth several LU.
    """
    return [
        *media.fade_chain(config.trim.fade_ms, trimmed_duration),
        *media.pad_chain(config.trim.lead_in_ms, config.trim.lead_out_ms),
    ]


def _level_chain(config: PipelineConfig, gain_db: float) -> list[str]:
    return [
        f"volume={gain_db:.3f}dB",
        *media.limiter_chain(config.loudness.true_peak_db),
    ]


def _write_master(
    config: PipelineConfig,
    shaped: Path,
    destination: Path,
    gain_db: float,
) -> Path:
    return media.render(
        shaped,
        destination,
        filters=_level_chain(config, gain_db),
        sample_rate=config.audio.sample_rate,
        channels=config.audio.channels,
        codec="libmp3lame",
        bitrate=config.audio.master_bitrate,
    )


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    sources_path: Path | None = None,
    audio_root: Path | None = None,
    output_dir: Path | None = None,
    only: Iterable[str] | None = None,
    force: bool = False,
) -> NormalizeResult:
    console.step("Normalize")

    inventory = phrases_module.load(phrases_path)
    selected = phrases_module.filter_ids(inventory, only)

    audio_root = audio_root or paths.audio_root()
    output_dir = output_dir or paths.master_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    work_dir = paths.work_dir() / "normalize"
    work_dir.mkdir(parents=True, exist_ok=True)

    preferred = _preferred_takes(sources_path or paths.sources_path())
    manifest = manifest_module.Manifest.load()
    result = NormalizeResult()

    target = config.loudness.target_lufs
    measure_kwargs = {
        "target_lufs": target,
        "true_peak_db": config.loudness.true_peak_db,
        "loudness_range": config.loudness.loudness_range,
        "pad_below_seconds": config.loudness.short_clip_seconds,
    }

    for phrase in selected:
        destination = output_dir / phrase.filename

        candidate = takes.find(
            phrase.id,
            audio_root=audio_root,
            preferred_take=preferred.get(phrase.id),
        )
        if candidate is None:
            if phrase.required:
                result.missing_required.append(phrase.id)
            else:
                result.missing_optional.append(phrase.id)
            continue

        if destination.is_file() and not force:
            console.detail(f"skip (exists) {destination.name}")
            result.skipped.append(phrase.id)
            continue

        try:
            staged = work_dir / f"{phrase.id}.wav"
            media.render(
                candidate.path,
                staged,
                filters=_trim_chain(config),
                sample_rate=config.audio.sample_rate,
                channels=config.audio.channels,
            )
            trimmed_duration = media.duration_seconds(staged)

            shaped = work_dir / f"{phrase.id}__shaped.wav"
            media.render(
                staged,
                shaped,
                filters=_shape_chain(config, trimmed_duration),
                sample_rate=config.audio.sample_rate,
                channels=config.audio.channels,
            )

            measured = media.measure_loudness(shaped, **measure_kwargs)

            if measured.is_silent:
                console.error(
                    f"{phrase.id}: {candidate.path.name} measures as silence "
                    f"({measured.integrated_lufs:.1f} LUFS). Check the timestamps."
                )
                result.failures.append(phrase.id)
                continue

            gain_db = target - measured.integrated_lufs
            _write_master(config, shaped, destination, gain_db)
            verified = media.measure_loudness(destination, **measure_kwargs)

            # MP3 encoding and the true-peak limiter can both nudge the result.
            # One corrective pass closes the gap; without it the shortest
            # prompts drift a couple of LU below everything else, which is
            # exactly the inconsistency this step exists to prevent.
            residual = target - verified.integrated_lufs
            if abs(residual) > _CORRECTION_THRESHOLD_LU and not verified.is_silent:
                gain_db += residual
                _write_master(config, shaped, destination, gain_db)
                verified = media.measure_loudness(destination, **measure_kwargs)
        except media.MediaError as error:
            console.error(f"{phrase.id}: {error}")
            result.failures.append(phrase.id)
            continue

        deviation = abs(verified.integrated_lufs - target)
        is_outlier = deviation > config.loudness.tolerance_lu
        if is_outlier:
            result.outliers.append(phrase.id)

        clip = NormalizedClip(
            phrase_id=phrase.id,
            path=destination,
            input_lufs=measured.integrated_lufs,
            output_lufs=verified.integrated_lufs,
            output_true_peak_db=verified.true_peak_db,
            gain_db=gain_db,
            origin=candidate.origin,
        )
        result.normalized.append(clip)

        record = manifest.record(phrase.id)
        record.master_path = str(destination)
        record.input_lufs = measured.integrated_lufs
        record.output_lufs = verified.integrated_lufs
        record.output_true_peak_db = verified.true_peak_db
        record.gain_applied_db = gain_db
        record.loudness_measured_on_padded = measured.measured_on_padded
        record.duration_seconds = media.duration_seconds(destination)
        if not record.origin:
            record.origin = (
                manifest_module.ORIGIN_SYNTHESIZED
                if candidate.is_synthesized
                else manifest_module.ORIGIN_EXTRACTED
            )
        if is_outlier:
            record.add_warning(
                f"Final loudness {verified.integrated_lufs:.1f} LUFS is "
                f"{deviation:.1f} LU from the {target} LUFS target."
            )
        record.mark_stage("normalize")

        flag = "  <-- outlier" if is_outlier else ""
        console.ok(
            f"{destination.name:<28} {measured.integrated_lufs:>7.1f} -> "
            f"{verified.integrated_lufs:>6.1f} LUFS  (gain {gain_db:+.1f} dB, "
            f"TP {verified.true_peak_db:+.1f} dB, from {candidate.origin}){flag}"
        )

    manifest.save()
    changed = phrases_module.set_statuses(
        phrases_path or paths.phrases_path(), manifest.status_updates()
    )
    if changed:
        console.detail(f"Updated {changed} phrase status value(s) in phrases.json")

    console.info(f"Normalized {len(result.normalized)} clip(s) to {target} LUFS.")

    if result.outliers:
        console.bullets(
            f"Clips more than {config.loudness.tolerance_lu} LU from target "
            "(usually heavy background noise or clipping in the source):",
            result.outliers,
        )
    if result.missing_required:
        console.bullets("Missing required clips (no audio found):", result.missing_required)
    if result.missing_optional:
        console.bullets("Missing optional clips:", result.missing_optional)

    return result
