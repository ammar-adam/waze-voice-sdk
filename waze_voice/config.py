"""Pipeline defaults loaded from config/pipeline.json.

Audio targets belong in config, not scattered through argparse defaults, so that
extraction, synthesis, normalization, and QA all agree on sample rate and
loudness without the user passing the same flags to four scripts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 44100
    channels: int = 1
    intermediate_format: str = "wav"
    master_format: str = "mp3"
    master_bitrate: str = "128k"


@dataclass(frozen=True)
class LoudnessConfig:
    target_lufs: float = -16.0
    true_peak_db: float = -1.5
    loudness_range: float = 11.0
    # EBU R128 integrated loudness is unreliable on very short material because
    # of the 400 ms block gating. Navigation prompts are routinely 0.8-2.0 s, so
    # anything under this threshold is matched by RMS instead. See docs/audio-targets.md.
    short_clip_seconds: float = 3.0
    # A clip whose measured loudness lands further than this from target after
    # normalization is reported as an outlier.
    tolerance_lu: float = 1.5


@dataclass(frozen=True)
class TrimConfig:
    """Silence handling applied during normalization."""

    enabled: bool = True
    threshold_db: float = -45.0
    lead_in_ms: int = 60
    lead_out_ms: int = 120
    fade_ms: int = 15


@dataclass(frozen=True)
class ExtractConfig:
    # Micro fades applied at cut boundaries so hard cuts do not click.
    edge_fade_ms: int = 20
    # Input-side seek preroll. Keeps seeking fast on long source files while
    # still letting the decoder settle before the output-side accurate cut.
    seek_preroll_seconds: float = 2.0
    min_duration_seconds: float = 0.15
    max_duration_seconds: float = 15.0


@dataclass(frozen=True)
class CleanConfig:
    mode: str = "ffmpeg"  # copy | ffmpeg | demucs
    demucs_model: str = "htdemucs"
    demucs_device: str = "cpu"
    # Applied after separation (or on its own in ffmpeg mode).
    highpass_hz: int = 70
    lowpass_hz: int = 12000
    denoise: bool = True
    # afftdn noise floor in dB. Higher values remove more, and remove it more
    # indiscriminately: at -25 the filter will erase a quiet, steady delivery
    # along with the hiss. ffmpeg's own default is -50.
    denoise_floor_db: float = -45.0
    # If cleaning drops a clip by more than this, the result is discarded and
    # the unprocessed clip is kept instead. A denoiser that eats the signal
    # fails silently otherwise, and a silent prompt is worse than a noisy one.
    max_loss_lu: float = 12.0


@dataclass(frozen=True)
class SynthConfig:
    backend: str = "xtts"  # xtts | finetuned
    model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    language: str = "en"
    reference_seconds: float = 12.0
    max_reference_clips: int = 12
    device: str = "cpu"


@dataclass(frozen=True)
class QAConfig:
    step_gap_seconds: float = 1.6
    phrase_gap_seconds: float = 0.12
    lead_silence_seconds: float = 0.4


@dataclass(frozen=True)
class PipelineConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    loudness: LoudnessConfig = field(default_factory=LoudnessConfig)
    trim: TrimConfig = field(default_factory=TrimConfig)
    extract: ExtractConfig = field(default_factory=ExtractConfig)
    clean: CleanConfig = field(default_factory=CleanConfig)
    synth: SynthConfig = field(default_factory=SynthConfig)
    qa: QAConfig = field(default_factory=QAConfig)


_SECTIONS: dict[str, type] = {
    "audio": AudioConfig,
    "loudness": LoudnessConfig,
    "trim": TrimConfig,
    "extract": ExtractConfig,
    "clean": CleanConfig,
    "synth": SynthConfig,
    "qa": QAConfig,
}


def _build_section(section: str, values: Any) -> Any:
    cls = _SECTIONS[section]
    if not isinstance(values, dict):
        raise SystemExit(f"pipeline config section '{section}' must be an object.")
    known = {f for f in cls.__dataclass_fields__}
    unknown = sorted(set(values) - known)
    if unknown:
        raise SystemExit(
            f"Unknown key(s) in pipeline config section '{section}': {', '.join(unknown)}"
        )
    return cls(**values)


def load(path: Path | None = None) -> PipelineConfig:
    """Load pipeline defaults, falling back to built-ins when the file is absent."""
    path = path or paths.pipeline_config_path()
    if not path.is_file():
        return PipelineConfig()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from None

    if not isinstance(raw, dict):
        raise SystemExit(f"Expected a JSON object in {path}")

    sections: dict[str, Any] = {}
    for section in _SECTIONS:
        if section in raw:
            sections[section] = _build_section(section, raw[section])

    unknown = sorted(set(raw) - set(_SECTIONS) - {"schema_version", "description"})
    if unknown:
        raise SystemExit(f"Unknown pipeline config section(s): {', '.join(unknown)}")

    return PipelineConfig(**sections)
