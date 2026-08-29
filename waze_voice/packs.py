"""Several voice packs from one clone.

A pack is one voice. Building a second one means a second set of source media, a
second set of extracted clips, and a second export, and none of it should touch
the first. Before this existed the only separation was ``WVS_AUDIO_ROOT``, which
moved the audio but left the source inventory shared, so two packs quietly
fought over ``data/sources.sample.csv``.

Layout::

    packs/
      <name>/
        pack.json        metadata: label, the voice, notes
        sources.csv      this pack's clips and timestamps
        phrases.json     optional; falls back to config/phrases.json
        routes.json      optional; falls back to config/routes.sample.json
        pipeline.json    optional; falls back to config/pipeline.json
        audio/           extracted, processed, synthesized, master, export

Only ``pack.json`` is required. Everything else falls back to the shared config,
because the Waze slot list does not change with the voice filling it. A pack
needs its own inventory only when it changes wording, ``tts_text``, or budget
weights, and its own ``pipeline.json`` only when a voice needs different audio
handling.

``packs/`` is Git-ignored. It holds paths to your media and the audio built from
it, neither of which belongs in a public repository.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import paths

PACK_CONFIG_NAME = "pack.json"
SCHEMA_VERSION = 1

_README = """# Packs

One directory per voice. Everything here is Git-ignored: it holds paths to your
own media and the audio built from it.

    python scripts/wvs.py pack new my-voice --label "My voice"
    python scripts/wvs.py pack list
    python scripts/wvs.py run --pack my-voice

Each pack falls back to the shared `config/` files for anything it does not
override, so a pack usually needs only its own `sources.csv`.

Nothing in here should be committed. If you want to keep a pack's *configuration*
under version control, copy `pack.json` and `sources.csv` somewhere else and
un-ignore that path deliberately, having first checked the CSV does not point at
anything private.
"""


@dataclass
class Pack:
    """One voice pack's identity and layout."""

    name: str
    label: str = ""
    voice: str = ""
    notes: str = ""
    created_at: str = ""
    schema_version: int = SCHEMA_VERSION
    _root: Path | None = field(default=None, repr=False, compare=False)

    # -- layout ------------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root if self._root is not None else paths.pack_root(self.name)

    @property
    def config_path(self) -> Path:
        return self.root / PACK_CONFIG_NAME

    @property
    def audio_root(self) -> Path:
        return self.root / "audio"

    @property
    def sources_path(self) -> Path:
        return self.root / "sources.csv"

    @property
    def phrases_path(self) -> Path:
        return self.root / "phrases.json"

    @property
    def export_dir(self) -> Path:
        return self.audio_root / "export"

    @property
    def display_label(self) -> str:
        return self.label or self.name

    # -- state -------------------------------------------------------------

    @property
    def has_sources(self) -> bool:
        return self.sources_path.is_file()

    @property
    def overrides(self) -> list[str]:
        """Shared config files this pack replaces with its own."""
        found = []
        for name in ("phrases.json", "routes.json", "pipeline.json"):
            if (self.root / name).is_file():
                found.append(name)
        return found

    def master_count(self) -> int:
        master = self.audio_root / "master"
        return len(list(master.glob("*.mp3"))) if master.is_dir() else 0

    def pack_bytes(self) -> int:
        pack_dir = self.export_dir / "pack"
        if not pack_dir.is_dir():
            return 0
        return sum(path.stat().st_size for path in pack_dir.glob("*.mp3"))

    # -- persistence -------------------------------------------------------

    def save(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {key: value for key, value in asdict(self).items() if not key.startswith("_")}
        self.config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        return self.config_path


def _read_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return data


def exists(name: str) -> bool:
    return (paths.pack_root(name) / PACK_CONFIG_NAME).is_file()


def load(name: str) -> Pack:
    """Load a pack by name, or exit with the list of ones that do exist."""
    validated = paths.validate_pack_name(name)
    config_path = paths.pack_root(validated) / PACK_CONFIG_NAME

    if not config_path.is_file():
        available = [pack.name for pack in list_packs()]
        hint = f" Existing packs: {', '.join(available)}." if available else " No packs exist yet."
        raise SystemExit(
            f"No pack named {validated!r}.{hint}\n"
            f"Create it with: python scripts/wvs.py pack new {validated}"
        )

    data = _read_config(config_path)
    known = {"name", "label", "voice", "notes", "created_at", "schema_version"}
    payload = {key: value for key, value in data.items() if key in known}
    payload["name"] = validated
    return Pack(**payload, _root=paths.pack_root(validated))


def list_packs() -> list[Pack]:
    """Every pack in ``packs/``, sorted by name. Unreadable ones are skipped."""
    root = paths.packs_dir()
    if not root.is_dir():
        return []

    found: list[Pack] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / PACK_CONFIG_NAME).is_file():
            continue
        try:
            name = paths.validate_pack_name(entry.name)
        except SystemExit:
            continue
        try:
            data = _read_config(entry / PACK_CONFIG_NAME)
        except SystemExit:
            continue
        known = {"label", "voice", "notes", "created_at", "schema_version"}
        payload = {key: value for key, value in data.items() if key in known}
        found.append(Pack(name=name, **payload, _root=entry))
    return found


def create(
    name: str,
    *,
    label: str = "",
    voice: str = "",
    notes: str = "",
    copy_phrases: bool = False,
    copy_routes: bool = False,
) -> Pack:
    """Create a pack directory with a starter source CSV.

    The CSV is seeded with a commented header rather than left empty, because an
    empty file gives a less useful error than a file that shows the format.
    """
    validated = paths.validate_pack_name(name)
    if exists(validated):
        raise SystemExit(
            f"A pack named {validated!r} already exists at {paths.pack_root(validated)}"
        )

    pack = Pack(
        name=validated,
        label=label,
        voice=voice,
        notes=notes,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        _root=paths.pack_root(validated),
    )
    pack.root.mkdir(parents=True, exist_ok=True)
    pack.save()

    for directory in ("raw", "extracted", "processed", "synthesized", "master", "export"):
        (pack.audio_root / directory).mkdir(parents=True, exist_ok=True)

    if not pack.sources_path.is_file():
        sample = paths.data_dir() / "sources.sample.csv"
        header = "phrase_id,source_path,start,end,take,preferred,gain_db,notes\n"
        if sample.is_file():
            header = sample.read_text(encoding="utf-8").splitlines()[0] + "\n"
        pack.sources_path.write_text(header, encoding="utf-8")

    if copy_phrases:
        shared = paths.config_dir() / "phrases.json"
        if shared.is_file():
            pack.phrases_path.write_text(shared.read_text(encoding="utf-8"), encoding="utf-8")

    if copy_routes:
        shared = paths.config_dir() / "routes.sample.json"
        if shared.is_file():
            (pack.root / "routes.json").write_text(
                shared.read_text(encoding="utf-8"), encoding="utf-8"
            )

    _ensure_packs_readme()
    return pack


def _ensure_packs_readme() -> None:
    readme = paths.packs_dir() / "README.md"
    if not readme.is_file():
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(_README, encoding="utf-8")


def resolve_active() -> Pack | None:
    """The pack the current invocation is working on, if any."""
    name = paths.active_pack()
    return load(name) if name else None
