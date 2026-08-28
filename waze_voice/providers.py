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

import base64
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
    # Whether the provider has a set of voices at all. False means a voice is
    # an opaque id the caller supplies from somewhere else, so there is nothing
    # to validate a preset's voice against.
    has_catalogue = True
    # The request field that accepts plain-English delivery direction, if the
    # provider has one. A preset's `direction` is routed here. None means the
    # provider has no equivalent and direction is advisory only.
    direction_option: str | None = None
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
                f'    Windows:  $env:{cls.env_var} = "..."\n'
                f"    bash:     export {cls.env_var}=...\n"
                f"Get one at {cls.signup_url}"
            )
        return cls(key, model=model, options=options)

    @classmethod
    def key_present(cls) -> bool:
        return bool(os.environ.get(cls.env_var, "").strip())

    def list_voices(self) -> list[Voice]:
        raise NotImplementedError

    def synthesize(
        self,
        text: str,
        voice: str,
        destination: Path,
        options: dict | None = None,
    ) -> Path:
        """``options`` overrides the instance options for this call only."""
        raise NotImplementedError

    def _merged(self, options: dict | None) -> dict:
        return {**self.options, **(options or {})}


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
                    labels=tuple(str(value) for value in labels.values() if isinstance(value, str)),
                )
            )
        return [voice for voice in voices if voice.id]

    def synthesize(
        self,
        text: str,
        voice: str,
        destination: Path,
        options: dict | None = None,
    ) -> Path:
        merged = self._merged(options)
        query = urllib.parse.urlencode(
            {"output_format": str(merged.get("output_format", self.default_output_format))}
        )
        # safe="" so a slash in a voice id cannot walk the URL path.
        voice_segment = urllib.parse.quote(voice, safe="")
        url = f"{self.base_url}/v1/text-to-speech/{voice_segment}?{query}"

        payload: dict[str, object] = {"text": text, "model_id": self.model}
        settings = merged.get("voice_settings")
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
    direction_option = "instructions"
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

    def synthesize(
        self,
        text: str,
        voice: str,
        destination: Path,
        options: dict | None = None,
    ) -> Path:
        merged = self._merged(options)
        payload: dict[str, object] = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        instructions = merged.get("instructions")
        if isinstance(instructions, str) and instructions.strip():
            payload["instructions"] = instructions
        speed = merged.get("speed")
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


class Hume(TtsProvider):
    """https://hume.ai - Octave, which designs a voice from a description.

    Octave is the closest fit to what a character preset actually is. Where the
    others take a catalogue voice and let you nudge its delivery, Octave takes
    the description itself as the primary input: pass a written character and it
    invents a voice to match, in the same call that speaks the line.

    That flexibility is also the trap. A description alone re-invents the voice
    on every request, and forty-three prompts each spoken by a slightly
    different bear is not a voice pack. So a saved voice id wins whenever there
    is one, and description-only synthesis is for auditioning, not for building.
    Use ``voicelab.design`` to audition and ``voicelab.save_design`` to freeze
    the winner, then set that id as the preset's voice.
    """

    name = "hume"
    env_var = "HUME_API_KEY"
    signup_url = "https://platform.hume.ai"
    default_model = "octave"
    base_url = "https://api.hume.ai"
    supports_voice_listing = True
    direction_option = "description"
    extension = ".mp3"

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Hume-Api-Key": self.api_key}

    def list_voices(self) -> list[Voice]:
        url = f"{self.base_url}/v0/tts/voices?provider=CUSTOM_VOICE"
        raw = _request(url, headers=self._headers)
        payload = json.loads(raw.decode("utf-8"))
        voices = []
        for entry in payload.get("voices_page", payload.get("voices", [])):
            voice_id = str(entry.get("id", ""))
            if voice_id:
                voices.append(
                    Voice(
                        id=voice_id,
                        name=str(entry.get("name", "")),
                        description=str(entry.get("provider") or ""),
                    )
                )
        return voices

    def synthesize(
        self,
        text: str,
        voice: str,
        destination: Path,
        options: dict | None = None,
    ) -> Path:
        merged = self._merged(options)
        utterance: dict[str, object] = {"text": text}

        # A saved voice keeps all forty-three clips the same character. Falling
        # back to the description is auditioning, and is flagged as such.
        if voice:
            utterance["voice"] = {"id": voice, "provider": "CUSTOM_VOICE"}
            acting = merged.get("acting_instructions") or merged.get("description")
            if isinstance(acting, str) and acting.strip():
                utterance["description"] = acting
        else:
            description = merged.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ProviderError(
                    "hume needs either a saved voice id or a description.\n"
                    "Audition with `voicelab.design`, save the one you want, "
                    "then set its id as the preset's voice."
                )
            utterance["description"] = description

        speed = merged.get("speed")
        if isinstance(speed, (int, float)):
            utterance["speed"] = float(speed)

        payload: dict[str, object] = {
            "utterances": [utterance],
            "num_generations": 1,
            "format": {"type": "mp3"},
        }

        raw = _request(
            f"{self.base_url}/v0/tts",
            headers=self._headers,
            payload=payload,
            method="POST",
        )
        body = json.loads(raw.decode("utf-8"))
        generations = body.get("generations") or []
        if not generations:
            raise ProviderError(f"hume returned no audio for {text[:40]!r}")

        encoded = generations[0].get("audio") or ""
        if not encoded:
            raise ProviderError("hume returned a generation with no audio payload.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(encoded))
        return destination


class FishAudio(TtsProvider):
    """https://fish.audio - a community model host, addressed by reference id.

    Unlike the other backends there is no fixed catalogue: a voice is whatever
    model id you point at, taken from the last path segment of a model's page
    URL. That makes the provider a thin pipe, and puts the choice of model, and
    the rights that come with it, entirely on the caller.

    Two operational consequences worth designing around. Models are
    user-uploaded and can disappear, so a pack is reproducible only as long as
    its model stays up; the exported audio survives, the ability to regenerate
    one line does not. And the response is raw audio rather than JSON, so
    failures arrive as an HTTP status rather than a message in a body.
    """

    name = "fish"
    env_var = "FISH_AUDIO_API_KEY"
    has_catalogue = False
    signup_url = "https://fish.audio"
    default_model = "s2.1-pro"
    base_url = "https://api.fish.audio"
    supports_voice_listing = False
    # Fish exposes prosody controls, but no plain-English delivery field.
    direction_option = None
    extension = ".mp3"

    def list_voices(self) -> list[Voice]:
        raise ProviderError(
            "fish has no fixed catalogue. Pass the model id from its page URL: "
            "fish.audio/m/<id>/ becomes --voice <id>."
        )

    def synthesize(
        self,
        text: str,
        voice: str,
        destination: Path,
        options: dict | None = None,
    ) -> Path:
        merged = self._merged(options)
        if not voice:
            raise ProviderError(
                "fish needs a model id as the voice. Take it from the model "
                "page URL: fish.audio/m/<id>/ becomes --voice <id>."
            )

        payload: dict[str, object] = {
            "text": text,
            "reference_id": voice,
            "format": "mp3",
            # 128k in, so our own bitrate allocation is the only lossy step
            # that matters. Anything lower here is a second generation loss we
            # cannot undo later.
            "mp3_bitrate": int(merged.get("mp3_bitrate", 128)),
        }
        for passthrough in ("temperature", "top_p", "prosody", "chunk_length"):
            if passthrough in merged:
                payload[passthrough] = merged[passthrough]

        # The model lives in a header here, not the body.
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "model": str(merged.get("model", self.model)),
        }

        audio = _request(
            f"{self.base_url}/v1/tts",
            headers=headers,
            payload=payload,
            method="POST",
        )
        if not audio:
            raise ProviderError(f"fish returned no audio for {text[:40]!r}")
        if audio.lstrip()[:1] == b"{":
            raise ProviderError(f"fish returned an error instead of audio: {audio[:200]!r}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(audio)
        return destination


REGISTRY: dict[str, type[TtsProvider]] = {
    ElevenLabs.name: ElevenLabs,
    FishAudio.name: FishAudio,
    Hume.name: Hume,
    OpenAI.name: OpenAI,
}

NAMES = tuple(REGISTRY)


def get(name: str) -> type[TtsProvider]:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ProviderError(f"Unknown provider {name!r}. Available: {', '.join(NAMES)}") from None


def available() -> list[str]:
    """Providers with a key already in the environment."""
    return [name for name, cls in REGISTRY.items() if cls.key_present()]
