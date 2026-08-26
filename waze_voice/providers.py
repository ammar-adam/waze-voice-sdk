"""Hosted text-to-speech providers.

Recording forty-three prompts by hand is the worst part of building a pack, and
the local synthesis backends trade that for a multi-gigabyte PyTorch install.
This is the third option: an API key and nothing else.

Deliberately built on ``urllib`` from the standard library. The core pipeline
installs nothing, and that stays true here, so the *easiest* route to a finished
pack is also the one with no dependencies at all. A whole pack is about a
thousand characters of text, which is small enough that cost is rarely the
consideration people expect it to be.

## Which voice

Every provider here ships a library of voices it licenses to you for use. Those
are the well-lit path: pick one, pass its id, done.

The API also accepts any voice id your account has, including ones you created
by cloning. This SDK passes the id through and cannot tell the difference. What
you are entitled to clone is between you, the person whose voice it is, and your
provider's terms, which universally require that you have the rights. See
LEGAL.md.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import console

USER_AGENT = "waze-voice-sdk"
REQUEST_TIMEOUT = 90
MAX_ATTEMPTS = 4


class ProviderError(RuntimeError):
    """Raised when a provider cannot be reached, or refuses a request."""


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    description: str = ""
    labels: tuple[str, ...] = field(default_factory=tuple)

    @property
    def summary(self) -> str:
        bits = [bit for bit in (self.description, ", ".join(self.labels)) if bit]
        return " - ".join(bits)


def _request(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict | None = None,
    method: str = "GET",
) -> bytes:
    """One HTTP call, retrying the failures that are worth retrying.

    429 and 5xx are transient and get a backoff. 401 and 400 are not: retrying a
    wrong API key four times just makes the user wait longer for the same
    answer.
    """
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("User-Agent", USER_AGENT)
    for key, value in headers.items():
        request.add_header(key, value)
    if body is not None:
        request.add_header("Content-Type", "application/json")

    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = ""
            # The status code carries the meaning; the body is a bonus.
            with contextlib.suppress(Exception):
                detail = error.read().decode("utf-8", "replace")[:400]

            if error.code in (401, 403):
                raise ProviderError(
                    f"{url} rejected the API key ({error.code}). Check the key is "
                    f"correct and has permission for this endpoint.\n{detail}"
                ) from None
            if error.code == 400:
                raise ProviderError(f"{url} rejected the request (400).\n{detail}") from None
            if error.code == 404:
                raise ProviderError(
                    f"{url} returned 404. Usually a voice id that does not exist on "
                    f"this account.\n{detail}"
                ) from None

            last_error = f"HTTP {error.code}: {detail}"
        except urllib.error.URLError as error:
            last_error = f"could not reach the provider ({error.reason})"
        except TimeoutError:
            last_error = f"timed out after {REQUEST_TIMEOUT}s"

        if attempt < MAX_ATTEMPTS:
            delay = 2 ** (attempt - 1)
            console.detail(f"retrying in {delay}s ({last_error})")
            time.sleep(delay)

    raise ProviderError(f"{url} failed after {MAX_ATTEMPTS} attempts. {last_error}")


class TtsProvider:
    """A hosted voice service."""

    name = ""
    env_var = ""
    signup_url = ""
    supports_voice_listing = True
    # Extension the provider's audio arrives in. Normalization re-encodes
    # everything anyway; this only decides what lands in audio/synthesized.
    extension = ".mp3"

    def __init__(self, api_key: str, *, model: str = "", options: dict | None = None) -> None:
        self.api_key = api_key
        self.model = model or self.default_model
        self.options = dict(options or {})

    default_model = ""

    @classmethod
    def from_env(cls, *, model: str = "", options: dict | None = None) -> TtsProvider:
        key = os.environ.get(cls.env_var, "").strip()
        if not key:
            raise ProviderError(
                f"{cls.name} needs an API key in ${cls.env_var}.\n"
                f"    Windows:  $env:{cls.env_var} = \"...\"\n"
                f"    bash:     export {cls.env_var}=...\n"
                f"Get one at {cls.signup_url}"
            )
        return cls(key, model=model, options=options)

    @classmethod
    def key_present(cls) -> bool:
        return bool(os.environ.get(cls.env_var, "").strip())

    def list_voices(self) -> list[Voice]:
        raise NotImplementedError

    def synthesize(self, text: str, voice: str, destination: Path) -> Path:
        raise NotImplementedError


class ElevenLabs(TtsProvider):
    """https://elevenlabs.io - large licensed voice library, plus cloning."""

    name = "elevenlabs"
    env_var = "ELEVENLABS_API_KEY"
    signup_url = "https://elevenlabs.io"
    default_model = "eleven_multilingual_v2"
    base_url = "https://api.elevenlabs.io"

    # mp3_44100_128 is available on every tier. wav_44100 avoids a lossy
    # generation before our own encode, but is not available on all plans, so it
    # is opt-in via synth.provider_options rather than the default.
    default_output_format = "mp3_44100_128"

    @property
    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.api_key}

    @property
    def output_format(self) -> str:
        return str(self.options.get("output_format", self.default_output_format))

    @property
    def extension(self) -> str:  # type: ignore[override]
        return ".wav" if self.output_format.startswith(("wav", "pcm")) else ".mp3"

    def list_voices(self) -> list[Voice]:
        raw = _request(f"{self.base_url}/v1/voices", headers=self._headers)
        payload = json.loads(raw.decode("utf-8"))
        voices = []
        for entry in payload.get("voices", []):
            labels = entry.get("labels") or {}
            voices.append(
                Voice(
                    id=str(entry.get("voice_id", "")),
                    name=str(entry.get("name", "")),
                    description=str(entry.get("description") or "")[:80],
                    labels=tuple(
                        str(value) for value in labels.values() if isinstance(value, str)
                    ),
                )
            )
        return [voice for voice in voices if voice.id]

    def synthesize(self, text: str, voice: str, destination: Path) -> Path:
        query = urllib.parse.urlencode({"output_format": self.output_format})
        # safe="" so a slash in a voice id cannot walk the URL path.
        voice_segment = urllib.parse.quote(voice, safe="")
        url = f"{self.base_url}/v1/text-to-speech/{voice_segment}?{query}"

        payload: dict[str, object] = {"text": text, "model_id": self.model}
        settings = self.options.get("voice_settings")
        if isinstance(settings, dict):
            payload["voice_settings"] = settings

        audio = _request(url, headers=self._headers, payload=payload, method="POST")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(audio)
        return destination


class OpenAI(TtsProvider):
    """https://platform.openai.com - stock voices only, no cloning.

    Worth knowing: because it has no cloning at all, every voice it can produce
    is one OpenAI licenses to you. That makes it the simplest option to reason
    about, and it takes a plain-English ``instructions`` string for delivery,
    which suits navigation prompts well.
    """

    name = "openai"
    env_var = "OPENAI_API_KEY"
    signup_url = "https://platform.openai.com"
    default_model = "gpt-4o-mini-tts"
    base_url = "https://api.openai.com"
    supports_voice_listing = False
    extension = ".mp3"

    # Fixed catalogue rather than an endpoint. Kept here so `wvs voices` works
    # without a key and without a network round trip.
    STOCK_VOICES = (
        ("alloy", "Neutral, even"),
        ("ash", "Warm, low"),
        ("ballad", "Soft, lyrical"),
        ("coral", "Bright, friendly"),
        ("echo", "Calm, measured"),
        ("fable", "Expressive, storytelling"),
        ("nova", "Crisp, energetic"),
        ("onyx", "Deep, authoritative"),
        ("sage", "Gentle, unhurried"),
        ("shimmer", "Light, upbeat"),
        ("verse", "Characterful, varied"),
    )

    def list_voices(self) -> list[Voice]:
        return [Voice(id=name, name=name, description=note) for name, note in self.STOCK_VOICES]

    def synthesize(self, text: str, voice: str, destination: Path) -> Path:
        payload: dict[str, object] = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        instructions = self.options.get("instructions")
        if isinstance(instructions, str) and instructions.strip():
            payload["instructions"] = instructions
        speed = self.options.get("speed")
        if isinstance(speed, (int, float)):
            payload["speed"] = float(speed)

        audio = _request(
            f"{self.base_url}/v1/audio/speech",
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload=payload,
            method="POST",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(audio)
        return destination


REGISTRY: dict[str, type[TtsProvider]] = {
    ElevenLabs.name: ElevenLabs,
    OpenAI.name: OpenAI,
}

NAMES = tuple(REGISTRY)


def get(name: str) -> type[TtsProvider]:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ProviderError(
            f"Unknown provider {name!r}. Available: {', '.join(NAMES)}"
        ) from None


def available() -> list[str]:
    """Providers with a key already in the environment."""
    return [name for name, cls in REGISTRY.items() if cls.key_present()]
