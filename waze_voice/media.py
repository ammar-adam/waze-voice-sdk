"""Thin, testable wrappers around ffmpeg / ffprobe / ffplay.

Everything that shells out to ffmpeg lives here. The rest of the SDK builds
filter chains and hands them to :func:`run_ffmpeg`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from . import console


class MediaError(RuntimeError):
    """Raised when an external media tool is missing or fails."""


_INSTALL_HINT = (
    "Install ffmpeg and make sure it is on PATH. On Windows:\n"
    "    winget install Gyan.FFmpeg\n"
    "Then open a new terminal so PATH is refreshed."
)


def find_tool(name: str) -> str | None:
    return shutil.which(name)


def require_tool(name: str) -> str:
    path = find_tool(name)
    if path is None:
        raise MediaError(f"'{name}' was not found on PATH.\n{_INSTALL_HINT}")
    return path


def run(command: Sequence[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command, raising :class:`MediaError` with real stderr on failure."""
    try:
        result = subprocess.run(
            list(command),
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except FileNotFoundError:
        raise MediaError(f"Command not found: {command[0]}\n{_INSTALL_HINT}") from None

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        tail = "\n".join(stderr.splitlines()[-12:])
        raise MediaError(
            f"{Path(command[0]).name} failed with exit code {result.returncode}.\n{tail}"
        )
    return result


def run_ffmpeg(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    ffmpeg = require_tool("ffmpeg")
    return run([ffmpeg, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", *args])


# --------------------------------------------------------------------------
# Probing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamInfo:
    duration: float
    sample_rate: int
    channels: int
    codec: str
    has_video: bool


def probe(path: Path) -> StreamInfo:
    """Return audio stream facts for ``path``."""
    ffprobe = require_tool("ffprobe")
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise MediaError(f"No audio stream found in {path}")

    duration = _first_float(
        audio.get("duration"),
        data.get("format", {}).get("duration"),
    )
    return StreamInfo(
        duration=duration,
        sample_rate=int(audio.get("sample_rate") or 0),
        channels=int(audio.get("channels") or 0),
        codec=str(audio.get("codec_name") or "unknown"),
        has_video=any(s.get("codec_type") == "video" for s in streams),
    )


def duration_seconds(path: Path) -> float:
    return probe(path).duration


def _first_float(*values: object) -> float:
    for value in values:
        try:
            if value is None:
                continue
            parsed = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return 0.0


# --------------------------------------------------------------------------
# Loudness
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Loudness:
    integrated_lufs: float
    true_peak_db: float
    loudness_range: float
    threshold_lufs: float
    measured_on_padded: bool

    @property
    def is_silent(self) -> bool:
        return self.integrated_lufs <= -70.0


_LOUDNORM_JSON = re.compile(r"\{[^{}]*input_i[^{}]*\}", re.DOTALL)


def measure_loudness(
    path: Path,
    *,
    target_lufs: float,
    true_peak_db: float,
    loudness_range: float,
    pad_below_seconds: float = 3.0,
) -> Loudness:
    """Measure EBU R128 integrated loudness, padding short clips first.

    ffmpeg's ``loudnorm`` gates on 400 ms blocks and warns that inputs shorter
    than roughly three seconds cannot be measured accurately. Navigation prompts
    are routinely under two seconds, so short clips are padded with digital
    silence before measurement. BS.1770 gating discards silent blocks (absolute
    gate at -70 LUFS plus the -10 LU relative gate), so the padding does not
    change the reported loudness of the speech itself. It only gives the
    measurement window enough material to run on.
    """
    info = probe(path)
    needs_pad = info.duration > 0 and info.duration < pad_below_seconds
    pad_amount = max(0.0, pad_below_seconds - info.duration) + 0.5 if needs_pad else 0.0

    filters = []
    if needs_pad:
        filters.append(f"apad=pad_dur={pad_amount:.3f}")
    filters.append(
        f"loudnorm=I={target_lufs}:TP={true_peak_db}:LRA={loudness_range}:print_format=json"
    )

    ffmpeg = require_tool("ffmpeg")
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-i",
            str(path),
            "-af",
            ",".join(filters),
            "-f",
            "null",
            "-",
        ],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").strip().splitlines()[-10:])
        raise MediaError(f"Loudness measurement failed for {path.name}.\n{tail}")

    match = _LOUDNORM_JSON.search(result.stderr or "")
    if match is None:
        raise MediaError(f"Could not parse loudnorm output for {path.name}.")

    payload = json.loads(match.group(0))
    return Loudness(
        integrated_lufs=_safe_float(payload.get("input_i"), -70.0),
        true_peak_db=_safe_float(payload.get("input_tp"), -99.0),
        loudness_range=_safe_float(payload.get("input_lra"), 0.0),
        threshold_lufs=_safe_float(payload.get("input_thresh"), -70.0),
        measured_on_padded=needs_pad,
    )


def _safe_float(value: object, fallback: float) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return fallback
    return parsed


# --------------------------------------------------------------------------
# Filter chain builders
# --------------------------------------------------------------------------


# Rebases the filter-chain timeline to zero. Without this, time-based filters
# such as afade see the source file's absolute timestamps: after seeking to
# 03:12 to cut a clip, `afade=t=out:st=1.1` is a time already long past, and the
# filter silences the entire clip instead of fading its tail. The failure is
# total and silent, so this is prepended to every chain that follows a seek.
RESET_TIMELINE = "asetpts=N/SR/TB"


def db_to_linear(db: float) -> float:
    return 10.0 ** (db / 20.0)


def trim_silence_chain(threshold_db: float) -> list[str]:
    """Strip leading and trailing silence from a clip."""
    trim = (
        "silenceremove=start_periods=1:start_silence=0:"
        f"start_threshold={threshold_db}dB:detection=peak"
    )
    return [trim, "areverse", trim, "areverse"]


def pad_chain(lead_in_ms: int, lead_out_ms: int) -> list[str]:
    chain: list[str] = []
    if lead_in_ms > 0:
        chain.append(f"adelay={lead_in_ms}:all=1")
    if lead_out_ms > 0:
        chain.append(f"apad=pad_dur={lead_out_ms / 1000.0:.3f}")
    return chain


def fade_chain(fade_ms: int, duration: float) -> list[str]:
    """Short fades at both edges so cuts do not click."""
    if fade_ms <= 0 or duration <= 0:
        return []
    fade = min(fade_ms / 1000.0, max(duration / 4.0, 0.001))
    fade_out_start = max(0.0, duration - fade)
    return [
        f"afade=t=in:st=0:d={fade:.4f}",
        f"afade=t=out:st={fade_out_start:.4f}:d={fade:.4f}",
    ]


def limiter_chain(true_peak_db: float) -> list[str]:
    limit = db_to_linear(true_peak_db)
    return [
        f"alimiter=level_in=1:level_out=1:limit={limit:.6f}:attack=5:release=50:level=disabled"
    ]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render(
    source: Path,
    destination: Path,
    *,
    filters: Sequence[str] = (),
    sample_rate: int = 44100,
    channels: int = 1,
    codec: str | None = None,
    bitrate: str | None = None,
    extra_input_args: Sequence[str] = (),
    extra_output_args: Sequence[str] = (),
) -> Path:
    """Render ``source`` to ``destination`` through an ffmpeg filter chain."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    args: list[str] = [*extra_input_args, "-i", str(source), "-vn", "-map_metadata", "-1"]

    chain = [RESET_TIMELINE, *[f for f in filters if f]]
    if chain:
        args += ["-af", ",".join(chain)]

    args += ["-ac", str(channels), "-ar", str(sample_rate)]
    if codec:
        args += ["-codec:a", codec]
    if bitrate:
        args += ["-b:a", bitrate]
    args += list(extra_output_args)
    args.append(str(destination))

    run_ffmpeg(args)
    return destination


def cut(
    source: Path,
    destination: Path,
    *,
    start: float,
    duration: float,
    preroll: float,
    filters: Sequence[str] = (),
    sample_rate: int = 44100,
    channels: int = 1,
) -> Path:
    """Cut a clip using a fast input seek plus an in-graph accurate trim.

    Input-side ``-ss`` gets the decoder close to the cut cheaply, which matters
    when the source is a two-hour recording, and gives a lossy decoder a moment
    to settle before the region of interest. ``atrim`` then makes the actual cut
    inside the filter graph.

    The obvious alternative, pairing input ``-ss`` with an output-side
    ``-ss``/``-t``, is wrong here: output seeking is applied *after* the filter
    graph. A fade-out positioned at 1.18 s would be applied 1.18 s into the
    whole remaining stream, and the output seek would then select a region the
    fade had already silenced. That failure is total and silent.
    """
    seek_start = max(0.0, start - preroll)
    inner_offset = start - seek_start

    destination.parent.mkdir(parents=True, exist_ok=True)
    args = ["-ss", f"{seek_start:.4f}", "-i", str(source), "-vn", "-map_metadata", "-1"]

    chain = [
        f"atrim=start={inner_offset:.4f}:duration={duration:.4f}",
        RESET_TIMELINE,
        *[f for f in filters if f],
    ]
    args += ["-af", ",".join(chain)]
    args += ["-ac", str(channels), "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(destination)]
    run_ffmpeg(args)
    return destination


def concat_with_gaps(
    clips: Sequence[tuple[Path, float]],
    destination: Path,
    *,
    lead_silence: float = 0.0,
    sample_rate: int = 44100,
    channels: int = 1,
    bed: Path | None = None,
    bed_gain_db: float = -20.0,
) -> Path:
    """Render clips into one continuous file, each followed by a silence gap.

    ``clips`` is a sequence of ``(path, trailing_gap_seconds)`` pairs. When a
    ``bed`` file is supplied it is looped underneath at ``bed_gain_db`` so a
    route can be auditioned against road noise.
    """
    if not clips:
        raise MediaError("Nothing to render: the clip sequence is empty.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    args: list[str] = []
    for path, _ in clips:
        args += ["-i", str(path)]

    parts: list[str] = []
    labels: list[str] = []
    for index, (_, gap) in enumerate(clips):
        chain = [f"[{index}:a]aformat=sample_rates={sample_rate}:channel_layouts=mono"]
        if index == 0 and lead_silence > 0:
            chain.append(f"adelay={int(lead_silence * 1000)}:all=1")
        if gap > 0:
            chain.append(f"apad=pad_dur={gap:.3f}")
        label = f"c{index}"
        parts.append(",".join(chain) + f"[{label}]")
        labels.append(f"[{label}]")

    joined_labels = "".join(labels)
    parts.append(f"{joined_labels}concat=n={len(clips)}:v=0:a=1[voice]")

    if bed is not None:
        args += ["-stream_loop", "-1", "-i", str(bed)]
        bed_index = len(clips)
        parts.append(
            f"[{bed_index}:a]aformat=sample_rates={sample_rate}:channel_layouts=mono,"
            f"volume={bed_gain_db}dB[bed]"
        )
        parts.append("[voice][bed]amix=inputs=2:duration=first:dropout_transition=0[out]")
        output_label = "[out]"
    else:
        output_label = "[voice]"

    args += [
        "-filter_complex",
        ";".join(parts),
        "-map",
        output_label,
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        str(destination),
    ]
    run_ffmpeg(args)
    return destination


def silence(destination: Path, seconds: float, *, sample_rate: int = 44100) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t",
            f"{seconds:.3f}",
            str(destination),
        ]
    )
    return destination


def play(path: Path) -> None:
    """Play a file synchronously, preferring ffplay and falling back to WinMM."""
    ffplay = find_tool("ffplay")
    if ffplay:
        run([ffplay, "-nodisp", "-autoexit", "-loglevel", "error", str(path)])
        return

    if path.suffix.lower() != ".wav":
        raise MediaError(
            "ffplay was not found on PATH and the Windows fallback player only "
            f"handles WAV files (got {path.suffix}).\n{_INSTALL_HINT}"
        )

    console.warn("ffplay not found; using the Windows SoundPlayer fallback.")
    escaped = str(path).replace("'", "''")
    run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"(New-Object Media.SoundPlayer '{escaped}').PlaySync();",
        ]
    )
