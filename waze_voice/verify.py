"""Pull an uploaded pack back down and prove it is what you sent.

Uploading reports success as soon as the server accepts the request. That is not
the same as the pack being right: the placeholder audio some workflows leave
behind, a file the server dropped, or a truncated archive all survive a
"successful" upload. The only real proof is fetching the pack back from Waze and
comparing it against what is on disk.

Every pack is downloadable at ``voice-prompts-ipv6.waze.com/<UUID>.tar.gz`` with
no authentication, which is what makes this possible, and is also why the UUID
should be treated as a secret.
"""

from __future__ import annotations

import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import console, media, wazepack

DOWNLOAD_TIMEOUT = 120

# A clip this quiet is a placeholder, not a prompt. Three of eleven real packs
# ship TickerPoints deliberately silent, so silence alone is not a failure; a
# pack that is mostly silence is.
SILENT_LUFS = -60.0


@dataclass
class VerifyResult:
    uuid: str = ""
    downloaded_bytes: int = 0
    remote_files: list[str] = field(default_factory=list)
    unknown_files: list[str] = field(default_factory=list)
    missing_core: list[str] = field(default_factory=list)
    silent_files: list[str] = field(default_factory=list)
    size_mismatches: list[str] = field(default_factory=list)
    only_local: list[str] = field(default_factory=list)
    only_remote: list[str] = field(default_factory=list)
    compared_against_local: bool = False

    @property
    def ok(self) -> bool:
        return (
            bool(self.remote_files)
            and not self.unknown_files
            and not self.missing_core
            and not self.size_mismatches
            and not self.only_local
        )


def download(uuid: str, destination: Path) -> int:
    """Fetch the pack tarball Waze holds for this UUID."""
    url = wazepack.BACKUP_DOWNLOAD_TEMPLATE.format(uuid=uuid)
    console.detail(f"GET {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "waze-voice-sdk"})
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"Waze returned HTTP {error.code} for {uuid}.\n"
            "A 403 or 404 usually means the UUID is wrong, or the upload did not "
            "actually land. Check the link the uploader printed."
        ) from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise SystemExit(f"Could not reach Waze to verify {uuid}: {error}") from None

    destination.write_bytes(payload)
    return len(payload)


def _extract(archive: Path, into: Path) -> list[Path]:
    into.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                # Never let an archive write outside the directory we chose.
                name = Path(member.name).name
                if not member.isfile() or not name:
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                (into / name).write_bytes(extracted.read())
    except tarfile.TarError as error:
        raise SystemExit(
            f"Downloaded file is not a readable tar.gz ({error}). The upload may "
            "have been truncated."
        ) from None
    return sorted(into.glob("*.mp3"))


def run(uuid: str, *, local_pack: Path | None = None) -> VerifyResult:
    """Download, unpack, and check. With ``local_pack``, also compare file for file."""
    console.step(f"Verifying {uuid}")
    result = VerifyResult(uuid=uuid)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        archive = work / "pack.tar.gz"
        result.downloaded_bytes = download(uuid, archive)
        console.ok(f"Downloaded {result.downloaded_bytes / 1000:.1f} kB")

        files = _extract(archive, work / "unpacked")
        result.remote_files = sorted(path.name for path in files)
        console.ok(f"Archive contains {len(files)} mp3 file(s)")

        names = set(result.remote_files)
        result.unknown_files = sorted(wazepack.unknown_filenames(names))
        result.missing_core = sorted(wazepack.core_filenames() - names)

        for path in files:
            try:
                loudness = media.measure_loudness(
                    path, target_lufs=-16.0, true_peak_db=-1.5, loudness_range=11.0
                )
            except media.MediaError:
                result.silent_files.append(f"{path.name} (unreadable)")
                continue
            if loudness.integrated_lufs <= SILENT_LUFS:
                result.silent_files.append(path.name)

        if local_pack is not None and local_pack.is_dir():
            result.compared_against_local = True
            local = {p.name: p for p in local_pack.glob("*.mp3")}
            result.only_local = sorted(set(local) - names)
            result.only_remote = sorted(names - set(local))
            for path in files:
                counterpart = local.get(path.name)
                if counterpart is None:
                    continue
                # Waze stores the bytes it was given, so sizes should match
                # exactly. Any difference means what is live is not what you
                # built: a placeholder, or an older revision.
                if counterpart.stat().st_size != path.stat().st_size:
                    result.size_mismatches.append(
                        f"{path.name}: local {counterpart.stat().st_size} B, "
                        f"remote {path.stat().st_size} B"
                    )

    _report(result)
    return result


def _report(result: VerifyResult) -> None:
    console.info("")
    console.table(
        [
            ("UUID", result.uuid),
            ("Downloaded", f"{result.downloaded_bytes / 1000:.1f} kB"),
            ("Files", f"{len(result.remote_files)} / {len(wazepack.VALID_FILENAMES)}"),
            ("Silent clips", str(len(result.silent_files))),
            (
                "Compared to local",
                "yes" if result.compared_against_local else "no (pass --pack-dir)",
            ),
        ],
        headers=("Field", "Value"),
    )

    console.bullets(
        "Files Waze will ignore (not on its list)", result.unknown_files
    )
    console.bullets("Core prompts missing from the live pack", result.missing_core)
    console.bullets(
        "Silent clips. Expected for TickerPoints; anywhere else means a "
        "placeholder survived",
        result.silent_files,
    )
    console.bullets(
        "Built locally but NOT in the live pack (the upload dropped these)",
        result.only_local,
    )
    console.bullets(
        "In the live pack but not built locally (left over from a previous pack)",
        result.only_remote,
    )
    console.bullets(
        "Byte-size mismatches: what is live is not what you built",
        result.size_mismatches,
    )

    console.info("")
    if result.ok:
        console.ok("Verified. The live pack matches what you uploaded.")
        console.detail(f"Share link: {wazepack.SHARE_LINK_TEMPLATE.format(uuid=result.uuid)}")
        console.detail("Treat that UUID as a secret: anyone holding it can download the pack.")
    else:
        console.error("Verification failed. The live pack is not what you intended.")
