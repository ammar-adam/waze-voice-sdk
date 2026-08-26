"""Environment check.

Every dependency problem in this pipeline surfaces the same way otherwise: a
step that ran fine yesterday dies halfway through with a stack trace from a
subprocess. This reports the whole picture up front, and says which steps each
missing piece actually blocks.
"""

from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass

from . import console, media, paths


@dataclass
class Check:
    name: str
    status: str  # ok | missing | warn
    detail: str
    blocks: str = ""

    @property
    def symbol(self) -> str:
        return {"ok": "[ok]", "warn": "[--]", "missing": "[!!]"}.get(self.status, "[??]")


def _tool_check(name: str, blocks: str, *, required: bool) -> Check:
    path = media.find_tool(name)
    if path:
        return Check(name, "ok", path)
    return Check(
        name,
        "missing" if required else "warn",
        "not on PATH",
        blocks,
    )


def _module_check(module: str, blocks: str, label: str | None = None) -> Check:
    label = label or module
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        spec = None

    if spec is None:
        return Check(label, "warn", "not installed", blocks)

    try:
        imported = importlib.import_module(module)
        version = getattr(imported, "__version__", "installed")
    except Exception:  # noqa: BLE001 - a broken install should not crash the doctor
        version = "installed (import failed)"
    return Check(label, "ok", str(version))


def _python_check() -> list[Check]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks = [Check("python", "ok", f"{version} ({platform.python_implementation()})")]

    # Unreachable if the interpreter is new enough to import this package at
    # all, but doctor is exactly where someone on an old Python looks first.
    if sys.version_info < (3, 10):  # noqa: UP036
        checks[0] = Check("python", "missing", f"{version}; 3.10 or newer required")
    return checks


def _config_check() -> list[Check]:
    checks: list[Check] = []
    for label, path in (
        ("config/phrases.json", paths.phrases_path()),
        ("config/routes.sample.json", paths.routes_path()),
        ("config/pipeline.json", paths.pipeline_config_path()),
    ):
        if path.is_file():
            checks.append(Check(label, "ok", "present"))
        else:
            status = "warn" if "pipeline" in label else "missing"
            detail = "missing (built-in defaults apply)" if status == "warn" else "missing"
            checks.append(Check(label, status, detail))
    return checks


def _gpu_detail() -> Check | None:
    if importlib.util.find_spec("torch") is None:
        return None
    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            return Check("cuda", "ok", f"{torch.cuda.get_device_name(0)}")
        return Check(
            "cuda",
            "warn",
            "not available; Demucs and TTS will run on CPU (slower but fine)",
        )
    except Exception:  # noqa: BLE001
        return None


def collect() -> list[Check]:
    checks: list[Check] = []
    checks += _python_check()
    checks.append(_tool_check("ffmpeg", "extract, clean, normalize, qa", required=True))
    checks.append(_tool_check("ffprobe", "validation and loudness measurement", required=True))
    checks.append(_tool_check("ffplay", "qa playback (a WAV-only fallback exists)", required=False))
    checks.append(_module_check("demucs", "clean --mode demucs (use --mode ffmpeg instead)"))
    checks.append(
        _module_check("chatterbox", "synth step (the default backend)", label="chatterbox-tts")
    )
    checks.append(
        _module_check("TTS", "synth --backend xtts (optional alternative)", label="coqui-tts")
    )
    checks.append(_module_check("torch", "demucs and synthesis backends"))
    checks.append(_module_check("torchaudio", "writing synthesized clips"))

    gpu = _gpu_detail()
    if gpu is not None:
        checks.append(gpu)

    checks += _config_check()
    return checks


def run() -> int:
    console.step("Doctor")
    console.info(f"Repository: {paths.repo_root()}")
    console.info(f"Platform:   {platform.system()} {platform.release()}")
    console.info("")

    checks = collect()
    width = max(len(check.name) for check in checks)
    for check in checks:
        line = f"  {check.symbol} {check.name.ljust(width)}  {check.detail}"
        print(line)
        if check.blocks and check.status != "ok":
            print(f"       {' ' * width}  blocks: {check.blocks}")

    blocking = [check for check in checks if check.status == "missing"]
    optional = [check for check in checks if check.status == "warn"]

    console.info("")
    if blocking:
        console.error(f"{len(blocking)} blocking problem(s). The core pipeline cannot run.")
        console.info("")
        console.info("  Install ffmpeg on Windows:")
        console.info("      winget install Gyan.FFmpeg")
        console.info("  Then open a new terminal so PATH picks it up.")
        return 1

    if optional:
        console.info(
            f"Core pipeline is ready. {len(optional)} optional component(s) unavailable; "
            "the steps above list what each one blocks."
        )
    else:
        console.info("Everything is available.")
    return 0
