"""Finding or inventing a voice, rather than settling for a catalogue one.

A stock voice plus delivery direction is a narration engine. It moves pace and
warmth; it does not move vocal identity, so every preset built on one ends up
sounding like the same reader in a different mood. Two ElevenLabs endpoints get
past that without imitating anybody's performance:

- **Voice Design** invents a voice from a written description. The result is a
  new vocal identity, not a stock voice wearing a hat.
- **The shared library** is thousands of existing voices, searchable.

The library needs care. Anyone can upload, and a voice *named* after a cartoon
character is usually somebody's clone of the copyrighted performance. The
category field is the thing to read: ``famous`` voices are licensed by
ElevenLabs under a deal with the speaker, ``professional`` ones come from a
verified speaker who consented. Everything else is unverified, and this module
labels it that way rather than quietly handing it over.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from . import console, providers

BASE_URL = "https://api.elevenlabs.io"

# Categories where a real person agreed to the voice being used.
CONSENTED_CATEGORIES = frozenset({"famous", "professional"})

DESIGN_MODEL = "eleven_multilingual_ttv_v2"

# Long enough that the model commits to a register rather than reading a label,
# and shaped like the job: a distance, a maneuver, an aside.
DEFAULT_AUDITION_TEXT = (
    "Oh. In four hundred meters, turn left, if you please. And then, at the "
    "roundabout, take the second exit. I counted twice, so I am fairly sure. "
    "There now. We have arrived, and I did say we would, didn't I?"
)


@dataclass
class LibraryVoice:
    voice_id: str
    name: str
    category: str = ""
    description: str = ""
    gender: str = ""
    age: str = ""
    accent: str = ""
    descriptive: str = ""
    preview_url: str = ""
    cloned_by_count: int = 0
    free_users_allowed: bool = True

    @property
    def consented(self) -> bool:
        """Whether the speaker is known to have agreed to this voice existing."""
        return self.category in CONSENTED_CATEGORIES

    @property
    def provenance(self) -> str:
        if self.category == "famous":
            return "licensed"
        if self.category == "professional":
            return "consented"
        return "UNVERIFIED"


@dataclass
class DesignPreview:
    generated_voice_id: str
    audio: bytes = field(repr=False, default=b"")
    duration_secs: float = 0.0
    text: str = ""


def _headers(api_key: str) -> dict[str, str]:
    return {"xi-api-key": api_key}


def search_library(
    api_key: str,
    *,
    search: str | None = None,
    category: str | None = None,
    page_size: int = 30,
    page: int = 0,
    **filters: str,
) -> list[LibraryVoice]:
    """List shared voices. ``category`` is professional, famous, or high_quality."""
    query: dict[str, str] = {"page_size": str(min(page_size, 100)), "page": str(page)}
    if search:
        query["search"] = search
    if category:
        query["category"] = category
    query.update({k: v for k, v in filters.items() if v})

    url = f"{BASE_URL}/v1/shared-voices?{urllib.parse.urlencode(query)}"
    raw = providers._request(url, headers=_headers(api_key))
    payload = json.loads(raw.decode("utf-8"))

    voices = []
    for entry in payload.get("voices", []):
        voice_id = str(entry.get("voice_id", ""))
        if not voice_id:
            continue
        voices.append(
            LibraryVoice(
                voice_id=voice_id,
                name=str(entry.get("name", "")),
                category=str(entry.get("category") or ""),
                description=str(entry.get("description") or "")[:200],
                gender=str(entry.get("gender") or ""),
                age=str(entry.get("age") or ""),
                accent=str(entry.get("accent") or ""),
                descriptive=str(entry.get("descriptive") or ""),
                preview_url=str(entry.get("preview_url") or ""),
                cloned_by_count=int(entry.get("cloned_by_count") or 0),
                free_users_allowed=bool(entry.get("free_users_allowed", True)),
            )
        )
    return voices


def design(
    api_key: str,
    description: str,
    *,
    text: str = DEFAULT_AUDITION_TEXT,
    guidance_scale: float = 5.0,
    loudness: float = 0.5,
    seed: int | None = None,
) -> list[DesignPreview]:
    """Invent voices from a written description. Returns previews to listen to.

    Nothing is saved: a preview costs a call and expires. ``save_design`` turns
    the one you pick into a real voice id.
    """
    payload: dict[str, object] = {
        "voice_description": description,
        "model_id": DESIGN_MODEL,
        "text": text,
        "guidance_scale": guidance_scale,
        "loudness": loudness,
    }
    if seed is not None:
        payload["seed"] = seed

    raw = providers._request(
        f"{BASE_URL}/v1/text-to-voice/design",
        headers=_headers(api_key),
        payload=payload,
        method="POST",
    )
    body = json.loads(raw.decode("utf-8"))

    previews = []
    for entry in body.get("previews", []):
        encoded = entry.get("audio_base_64") or ""
        previews.append(
            DesignPreview(
                generated_voice_id=str(entry.get("generated_voice_id", "")),
                audio=base64.b64decode(encoded) if encoded else b"",
                duration_secs=float(entry.get("duration_secs") or 0.0),
                text=str(entry.get("text") or ""),
            )
        )
    return previews


def save_design(api_key: str, generated_voice_id: str, name: str, description: str) -> str:
    """Promote a preview to a permanent voice. Returns the voice id."""
    raw = providers._request(
        f"{BASE_URL}/v1/text-to-voice",
        headers=_headers(api_key),
        payload={
            "voice_name": name,
            "voice_description": description,
            "generated_voice_id": generated_voice_id,
        },
        method="POST",
    )
    body = json.loads(raw.decode("utf-8"))
    return str(body.get("voice_id", ""))


def write_previews(previews: list[DesignPreview], directory: Path, stem: str) -> list[Path]:
    """Save previews so they can be listened to before one is chosen."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for index, preview in enumerate(previews, start=1):
        if not preview.audio:
            continue
        path = directory / f"{stem}__{index}.mp3"
        path.write_bytes(preview.audio)
        written.append(path)
        console.detail(
            f"{path.name}  {preview.duration_secs:.1f}s  id={preview.generated_voice_id}"
        )
    return written


# --------------------------------------------------------------------------
# Hume Octave
# --------------------------------------------------------------------------

HUME_BASE_URL = "https://api.hume.ai"


def design_hume(
    api_key: str,
    description: str,
    *,
    text: str = DEFAULT_AUDITION_TEXT,
    count: int = 3,
) -> list[DesignPreview]:
    """Invent voices from a description, Octave's way.

    Octave folds design into synthesis: the description rides along with the
    line rather than creating a voice first. Handy for auditioning, and exactly
    why the winner has to be saved before building a pack - an unsaved
    description is re-interpreted on every call.
    """
    raw = providers._request(
        f"{HUME_BASE_URL}/v0/tts",
        headers={"X-Hume-Api-Key": api_key},
        payload={
            "utterances": [{"text": text, "description": description}],
            "num_generations": count,
            "format": {"type": "mp3"},
        },
        method="POST",
    )
    body = json.loads(raw.decode("utf-8"))

    previews = []
    for entry in body.get("generations", []):
        encoded = entry.get("audio") or ""
        previews.append(
            DesignPreview(
                generated_voice_id=str(entry.get("generation_id", "")),
                audio=base64.b64decode(encoded) if encoded else b"",
                duration_secs=float(entry.get("duration") or 0.0),
                text=text,
            )
        )
    return previews


def save_hume(api_key: str, generation_id: str, name: str) -> str:
    """Freeze a generation into a reusable voice. Returns its id.

    Without this every prompt is a slightly different character, which reads as
    a broken pack rather than a stylistic choice.
    """
    raw = providers._request(
        f"{HUME_BASE_URL}/v0/tts/voices",
        headers={"X-Hume-Api-Key": api_key},
        payload={"generation_id": generation_id, "name": name},
        method="POST",
    )
    body = json.loads(raw.decode("utf-8"))
    return str(body.get("id") or body.get("name") or "")
