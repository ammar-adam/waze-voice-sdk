"""Step 3: synthesize the phrases that do not exist in the source media.

The default backend is **Chatterbox** (Resemble AI): zero-shot voice cloning that
conditions on about ten seconds of the user's own cleaned clips and speaks new
lines in that voice with no training run. It is MIT licensed including the model
weights, installs on current Python, and runs on CPU.

That combination is what a navigation pack needs. A pack yields well under a
minute of usable source audio, far below what fine-tuning wants and comfortably
above what zero-shot conditioning wants.

Two other backends remain available:

``xtts``
    Coqui XTTS-v2 through the community-maintained ``coqui-tts`` fork. Better
    multilingual coverage, but the *weights* are under the Coqui Public Model
    License, which is non-commercial, and Coqui Inc. is gone so nobody can sell
    you a commercial licence. Fine for personal use; a dead end for anything
    published commercially. See docs/tts.md.

``finetuned``
    A checkpoint the user trained themselves with ``tts/train.py``.

Nothing here ships weights, and nothing downloads a voice belonging to someone
else. The reference audio is whatever the user put in ``audio/processed``.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .. import (
    console,
    manifest as manifest_module,
    media,
    paths,
    phrases as phrases_module,
    takes,
)
from ..config import PipelineConfig

BACKENDS = ("chatterbox", "xtts", "finetuned")
CHATTERBOX_MODELS = ("turbo", "nano", "full", "multilingual")

CONSENT_RECEIPT = ".voice-consent"

_CONSENT_TEXT = """Voice synthesis gate
--------------------
This step clones a voice from the reference audio in audio/processed.

Confirm that you have the rights and, where a real person is involved, the
consent needed to synthesize this voice for your intended use. See LEGAL.md.

Re-run with --accept-voice-terms to record your acknowledgement and continue.
"""

_CHATTERBOX_HINT = (
    "Install the synthesis backend:\n"
    "    python -m pip install -r requirements-tts.txt\n"
    "It pulls in PyTorch, so expect a multi-GB download. See docs/tts.md."
)

_COQUI_HINT = (
    "The xtts backend needs the community-maintained Coqui fork:\n"
    "    python -m pip install coqui-tts\n"
    "Note that XTTS-v2 model weights are non-commercial. The default\n"
    "chatterbox backend is MIT licensed including weights. See docs/tts.md."
)


@dataclass
class SynthResult:
    synthesized: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    reference: Path | None = None
    backend: str = "chatterbox"

    @property
    def ok(self) -> bool:
        return not self.failures


# A backend is just a callable: speak this text, in this voice, to this file.
Speaker = Callable[[str, Path, Path | None], None]


# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def is_available(backend: str = "chatterbox") -> tuple[bool, str]:
    """Report whether a backend can run, and why not when it cannot.

    The orchestrator uses this to skip synthesis with one clear line rather than
    aborting a whole pipeline run over an optional dependency.
    """
    if backend == "chatterbox":
        if not _module_present("chatterbox"):
            return False, "Chatterbox is not installed (pip install -r requirements-tts.txt)"
        if not _module_present("torchaudio"):
            return False, "torchaudio is not installed (it ships with the chatterbox install)"
        return True, ""

    if backend in ("xtts", "finetuned"):
        # coqui-tts supports >=3.10,<3.15. The archived original `TTS` package
        # capped at 3.11; this is the maintained fork and does not.
        if sys.version_info >= (3, 15):
            return False, (
                f"coqui-tts does not support Python "
                f"{sys.version_info.major}.{sys.version_info.minor} (needs 3.10-3.14)"
            )
        if not _module_present("TTS"):
            return False, "coqui-tts is not installed (pip install coqui-tts)"
        return True, ""

    return False, f"Unknown backend {backend!r}"


def check_consent(*, accepted: bool, repo_root: Path | None = None) -> None:
    receipt = (repo_root or paths.repo_root()) / CONSENT_RECEIPT
    if receipt.is_file():
        return
    if not accepted:
        raise SystemExit(_CONSENT_TEXT)
    receipt.write_text(
        "Voice synthesis terms acknowledged via --accept-voice-terms.\n"
        "See LEGAL.md. This receipt is local and Git-ignored.\n",
        encoding="utf-8",
    )
    console.detail(f"Recorded acknowledgement in {receipt.name}")


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------


def _load_chatterbox(config: PipelineConfig) -> Speaker:
    """Zero-shot cloning with Chatterbox. Default backend."""
    variant = config.synth.model
    if variant not in CHATTERBOX_MODELS:
        raise SystemExit(
            f"Unknown chatterbox model {variant!r}. "
            f"Choose one of: {', '.join(CHATTERBOX_MODELS)}"
        )

    try:
        import torchaudio  # type: ignore[import-not-found]
    except ImportError as error:
        raise SystemExit(f"Could not import torchaudio ({error}).\n{_CHATTERBOX_HINT}") from None

    device = config.synth.device
    console.detail(f"Loading Chatterbox '{variant}' on {device}")
    console.detail("The first run downloads model weights; expect a wait.")

    try:
        if variant == "multilingual":
            from chatterbox.mtl_tts import (  # type: ignore[import-not-found]
                ChatterboxMultilingualTTS,
            )

            model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
        elif variant == "full":
            from chatterbox.tts import ChatterboxTTS  # type: ignore[import-not-found]

            model = ChatterboxTTS.from_pretrained(device=device)
        else:
            from chatterbox.tts_turbo import (  # type: ignore[import-not-found]
                ChatterboxTurboTTS,
            )

            model = ChatterboxTurboTTS.from_pretrained(
                device=device, **({"nano": True} if variant == "nano" else {})
            )
    except ImportError as error:
        raise SystemExit(f"Could not import Chatterbox ({error}).\n{_CHATTERBOX_HINT}") from None

    # Passed straight through to generate(). Kept open-ended rather than mapped
    # to named config fields, so a backend that adds or renames a knob does not
    # break this SDK. exaggeration and cfg_weight are the usual ones.
    extra = dict(config.synth.generate_options)
    if variant == "multilingual":
        extra.setdefault("language_id", config.synth.language)

    def speak(text: str, destination: Path, reference: Path | None) -> None:
        kwargs = dict(extra)
        if reference is not None:
            kwargs["audio_prompt_path"] = str(reference)
        wav = model.generate(text, **kwargs)
        destination.parent.mkdir(parents=True, exist_ok=True)
        torchaudio.save(str(destination), wav, model.sr)

    return speak


def _load_coqui(
    config: PipelineConfig,
    backend: str,
    model_path: Path | None,
    config_path: Path | None,
) -> Speaker:
    """XTTS-v2, or a checkpoint the user fine-tuned themselves."""
    available, reason = is_available(backend)
    if not available:
        raise SystemExit(f"{reason}.\n{_COQUI_HINT}")

    try:
        from TTS.api import TTS  # type: ignore[import-not-found]
    except ImportError as error:
        raise SystemExit(f"Could not import coqui-tts ({error}).\n{_COQUI_HINT}") from None

    if backend == "finetuned":
        if model_path is None:
            raise SystemExit(
                "--model-path is required for the 'finetuned' backend. Point it at "
                "the checkpoint directory produced by tts/train.py."
            )
        if not model_path.exists():
            raise SystemExit(f"Model path does not exist: {model_path}")
        console.detail(f"Loading fine-tuned model from {model_path}")
        model = TTS(
            model_path=str(model_path),
            config_path=str(config_path) if config_path else None,
            progress_bar=False,
        ).to(config.synth.device)
    else:
        console.warn(
            "XTTS-v2 weights are under the Coqui Public Model License, which is "
            "non-commercial, and Coqui Inc. no longer exists to license them "
            "otherwise. Use the default chatterbox backend for anything you intend "
            "to publish commercially."
        )
        console.detail(f"Loading {config.synth.coqui_model_name} on {config.synth.device}")
        console.detail("The first run downloads model weights; expect a wait.")
        model = TTS(config.synth.coqui_model_name, progress_bar=False).to(config.synth.device)

    def speak(text: str, destination: Path, reference: Path | None) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, object] = {"text": text, "file_path": str(destination)}
        if reference is not None:
            kwargs["speaker_wav"] = str(reference)
        if backend == "xtts" or getattr(model, "is_multi_lingual", False):
            kwargs["language"] = config.synth.language
        model.tts_to_file(**kwargs)

    return speak


def load_backend(
    config: PipelineConfig,
    backend: str,
    model_path: Path | None = None,
    model_config_path: Path | None = None,
) -> Speaker:
    if backend == "chatterbox":
        return _load_chatterbox(config)
    if backend in ("xtts", "finetuned"):
        return _load_coqui(config, backend, model_path, model_config_path)
    raise SystemExit(f"Unknown backend {backend!r}. Choose one of: {', '.join(BACKENDS)}")


# --------------------------------------------------------------------------
# Reference audio
# --------------------------------------------------------------------------


def build_reference(
    *,
    config: PipelineConfig,
    source_dir: Path | None = None,
    destination: Path | None = None,
) -> Path:
    """Concatenate the user's cleanest clips into one speaker reference file.

    Zero-shot backends condition better on a single continuous sample than on a
    pile of fragments, and longer references capture more of the voice's range.
    Clips are taken longest-first until the configured reference length is
    reached. Chatterbox is documented against a roughly ten-second reference.
    """
    source_dir = source_dir or paths.processed_dir()
    destination = destination or (paths.work_dir() / "tts_reference.wav")

    candidates = sorted(source_dir.glob("*.wav"))
    if not candidates:
        raise SystemExit(
            f"No cleaned clips found in {source_dir}.\n"
            "Run the extract and clean steps first: the synthesis step imitates "
            "your own clips, so it needs at least a few seconds of them."
        )

    measured: list[tuple[float, Path]] = []
    for path in candidates:
        try:
            measured.append((media.duration_seconds(path), path))
        except media.MediaError as error:
            console.warn(f"Skipping {path.name} as a reference: {error}")

    if not measured:
        raise SystemExit(f"None of the clips in {source_dir} could be probed.")

    measured.sort(reverse=True)

    chosen: list[tuple[Path, float]] = []
    total = 0.0
    for duration, path in measured:
        if total >= config.synth.reference_seconds:
            break
        if len(chosen) >= config.synth.max_reference_clips:
            break
        chosen.append((path, 0.25))  # short gap so words do not run together
        total += duration + 0.25

    if total < 6.0:
        console.warn(
            f"Only {total:.1f}s of reference audio available. Voice similarity falls "
            "off sharply below about six seconds; more source clips will help more "
            "than any setting here."
        )

    media.concat_with_gaps(
        chosen,
        destination,
        sample_rate=config.audio.sample_rate,
        channels=config.audio.channels,
    )
    console.detail(
        f"Built speaker reference from {len(chosen)} clip(s), {total:.1f}s: {destination.name}"
    )
    return destination


# --------------------------------------------------------------------------
# Gap detection
# --------------------------------------------------------------------------


def find_gaps(
    *,
    phrases_path: Path | None = None,
    audio_root: Path | None = None,
    include_optional: bool = False,
    only: Iterable[str] | None = None,
) -> list[phrases_module.Phrase]:
    """Phrases with no audio anywhere: the ones synthesis exists to fill."""
    inventory = phrases_module.load(phrases_path)
    audio_root = audio_root or paths.audio_root()

    selected = phrases_module.filter_ids(inventory, only)
    if not include_optional and not only:
        selected = [phrase for phrase in selected if phrase.required]

    return [
        phrase
        for phrase in selected
        if takes.find(phrase.id, audio_root=audio_root) is None
    ]


# --------------------------------------------------------------------------
# Synthesis
# --------------------------------------------------------------------------


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    output_dir: Path | None = None,
    backend: str | None = None,
    reference: Path | None = None,
    model_path: Path | None = None,
    model_config_path: Path | None = None,
    only: Iterable[str] | None = None,
    include_optional: bool = False,
    accept_voice_terms: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> SynthResult:
    console.step("Synthesize")

    backend = backend or config.synth.backend
    if backend not in BACKENDS:
        raise SystemExit(f"Unknown backend {backend!r}. Choose one of: {', '.join(BACKENDS)}")

    output_dir = output_dir or paths.synthesized_dir()
    result = SynthResult(backend=backend)

    gaps = find_gaps(
        phrases_path=phrases_path,
        include_optional=include_optional,
        only=only,
    )
    if force and only:
        inventory = phrases_module.load(phrases_path)
        gaps = phrases_module.filter_ids(inventory, only)

    result.gaps = [phrase.id for phrase in gaps]

    if not gaps:
        console.info("No gaps to fill: every selected phrase already has audio.")
        return result

    console.bullets(
        f"{len(gaps)} phrase(s) need synthesis:",
        [f"{phrase.id}: {phrase.speech_text}" for phrase in gaps],
    )

    if dry_run:
        console.info(f"Dry run: stopping before loading the '{backend}' backend.")
        return result

    # Check the dependency before the consent gate, so someone without the
    # backend installed gets install instructions rather than a rights prompt
    # for a step that cannot run anyway.
    available, reason = is_available(backend)
    if not available:
        raise SystemExit(
            f"{reason}.\n"
            + (_COQUI_HINT if backend in ("xtts", "finetuned") else _CHATTERBOX_HINT)
        )

    check_consent(accepted=accept_voice_terms)

    reference_path = reference or build_reference(config=config)
    result.reference = reference_path

    speak = load_backend(config, backend, model_path, model_config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_module.Manifest.load()

    for phrase in gaps:
        destination = output_dir / f"{phrase.id}.wav"
        if destination.is_file() and not force:
            console.detail(f"skip (exists) {destination.name}")
            result.skipped.append(phrase.id)
            continue

        try:
            speak(phrase.speech_text, destination, reference_path)
        except Exception as error:  # noqa: BLE001 - surface any backend failure per phrase
            console.error(f"{phrase.id}: synthesis failed ({error})")
            result.failures.append(phrase.id)
            continue

        if not destination.is_file():
            console.error(f"{phrase.id}: the backend reported success but wrote no file.")
            result.failures.append(phrase.id)
            continue

        record = manifest.record(phrase.id)
        record.origin = manifest_module.ORIGIN_SYNTHESIZED
        record.synthesized_path = str(destination)
        record.synth_backend = (
            f"{backend}:{config.synth.model}" if backend == "chatterbox" else backend
        )
        try:
            record.duration_seconds = media.duration_seconds(destination)
        except media.MediaError:
            record.add_warning("Could not probe the synthesized clip.")
        record.mark_stage("synth")

        console.ok(f'{destination.name}  "{phrase.speech_text}"')
        result.synthesized.append(destination)

    manifest.save()
    console.info(f"Synthesized {len(result.synthesized)} clip(s) with the '{backend}' backend.")
    if result.synthesized:
        console.detail(
            "Listen to these before shipping. Synthetic prompts drift in pace and "
            "emphasis more than cut source audio does."
        )
    return result


# --------------------------------------------------------------------------
# Dataset preparation for the fine-tuning path
# --------------------------------------------------------------------------


def prepare_dataset(
    *,
    phrases_path: Path | None = None,
    source_dir: Path | None = None,
    destination: Path | None = None,
) -> Path:
    """Write an LJSpeech-style dataset from cleaned clips and phrase labels.

    Only needed for the fine-tuning path. The default backend clones zero-shot
    and needs no dataset at all.
    """
    import csv
    import shutil

    inventory = phrases_module.load(phrases_path)
    source_dir = source_dir or paths.processed_dir()
    destination = destination or (paths.repo_root() / "datasets" / "voice")

    wavs_dir = destination / "wavs"
    wavs_dir.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[str, str, str]] = []
    for phrase in inventory:
        for candidate in takes.find_all(phrase.id):
            if candidate.origin != "processed":
                continue
            name = candidate.path.stem
            shutil.copy2(candidate.path, wavs_dir / f"{name}.wav")
            rows.append((name, phrase.speech_text, phrase.speech_text))

    if not rows:
        raise SystemExit(
            f"No cleaned clips found in {source_dir}. Run extract and clean first."
        )

    metadata = destination / "metadata.csv"
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|", lineterminator="\n")
        writer.writerows(rows)

    console.ok(f"Wrote {len(rows)} dataset row(s) to {metadata}")
    console.detail(
        "Transcripts come from phrases.json labels. Fix any clip whose audio does "
        "not match its label before training, or the model learns the mismatch."
    )
    return destination
