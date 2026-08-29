"""Build a preset and stage it where the community uploader will actually find it.

The manual version of this is three steps with two traps in them: the staging
directory is ``mp3_upload/input_packs``, not the uploader's repository root, and
the folder name you choose there becomes the voice name Waze shows the driver.
Getting either wrong is quiet - the uploader ingests nothing, or publishes a
pack called ``pooh``.

This refuses to stage a pack the build did not bless. Waze rejects an oversized
pack silently, so the manifest verdict is the only warning anyone gets.

    python scripts/stage_for_upload.py --preset pooh --name "Winnie the Pooh"
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from waze_voice import wazepack  # noqa: E402
from waze_voice.steps import export as export_step  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_UPLOADER = REPO.parent / "waze-voicepack-links"


def _fail(message: str) -> int:
    print(f"\n[stop] {message}")
    return 1


def build(preset: str, pack: str, *, provider: str = "", voice: str = "") -> int:
    """``provider`` and ``voice`` override the preset's own, keeping its script.

    That separation is the useful one: the lines are the character's writing and
    the voice is how it is spoken, so the same 43 lines can be sent through a
    catalogue voice or a community model without maintaining two copies of them.
    """
    command = [
        sys.executable,
        str(REPO / "scripts" / "wvs.py"),
        "quickstart",
        "--pack",
        pack,
        "--preset",
        preset,
        "--accept-voice-terms",
    ]
    if provider:
        command += ["--provider", provider]
    if voice:
        command += ["--voice", voice]
    print(f"$ {' '.join(command[1:])}\n")
    return subprocess.run(command, cwd=str(REPO)).returncode


def stage(pack_dir: Path, uploader: Path, name: str) -> int:
    mp3s = sorted(pack_dir.glob("*.mp3"))
    if not mp3s:
        return _fail(f"No mp3 files in {pack_dir}. Did the build run?")

    # Checking names rather than counting them. A count rejects a legitimate
    # single-unit pack, which is 39 files rather than 43, while still passing a
    # pack of 43 files with one of them misnamed - the case that actually hurts,
    # because the uploader ingests whatever it recognises and silently drops the
    # rest.
    names = {path.name for path in mp3s}
    if unknown := wazepack.unknown_filenames(names):
        return _fail(
            f"{len(unknown)} file(s) Waze does not recognise and would silently "
            f"ignore: {', '.join(sorted(unknown))}"
        )

    missing = wazepack.core_filenames() - names
    # A single-unit pack is missing the other system's distances by design, so
    # it only has to be complete for one of them.
    if missing:
        for units in (wazepack.UNITS_METRIC, wazepack.UNITS_IMPERIAL):
            if not wazepack.core_filenames(units) - names:
                print(f"  [note] {units}-only pack: {len(mp3s)} files.")
                print("         Drivers on the other system hear Waze's own voice for distances.")
                break
        else:
            return _fail(
                f"{len(missing)} core prompt(s) missing: "
                f"{', '.join(sorted(missing))}.\n"
                "The uploader publishes a pack containing a single valid file "
                "without complaining, so this has to be caught here."
            )

    destination = uploader / "mp3_upload" / "input_packs" / name
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for path in mp3s:
        shutil.copy2(path, destination / path.name)

    # Every folder here is uploaded, not just the one staged now. A pack left
    # from an earlier run would go up again under a new UUID.
    stale = uploader / "mp3_upload" / "compressed_packs"
    leftovers = [p.name for p in stale.iterdir()] if stale.is_dir() else []
    if leftovers:
        print(f"  [warn] compressed_packs still holds {leftovers}.")
        print("         Delete those or they upload again under fresh UUIDs.")

    siblings = [
        p.name
        for p in (uploader / "mp3_upload" / "input_packs").iterdir()
        if p.is_dir() and p.name != name
    ]
    if siblings:
        print(f"  [note] other staged packs will also upload: {siblings}")

    print(f"\n  Staged {len(mp3s)} files as the voice name {name!r}.")
    print(f"  {destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", required=True)
    parser.add_argument(
        "--name",
        required=True,
        help="Folder name, and the voice name Waze shows the driver.",
    )
    parser.add_argument("--pack", help="Defaults to the preset name.")
    parser.add_argument("--uploader", type=Path, default=DEFAULT_UPLOADER)
    parser.add_argument("--skip-build", action="store_true", help="Stage an existing build.")
    args = parser.parse_args(argv)

    pack = args.pack or args.preset
    if not args.uploader.is_dir():
        return _fail(f"No uploader checkout at {args.uploader}. Pass --uploader.")

    if not args.skip_build and (code := build(args.preset, pack)):
        return _fail(f"Build failed (exit {code}). Nothing staged.")

    export_dir = REPO / "packs" / pack / "audio" / "export"
    manifest_path = export_dir / export_step.MANIFEST_NAME
    if not manifest_path.is_file():
        return _fail(f"No manifest at {manifest_path}. Did the build run?")

    budget = json.loads(manifest_path.read_text(encoding="utf-8"))["budget"]
    utilisation = budget["utilisation"]
    print(
        f"\n  Measured {budget['total_bytes'] / 1024 / 1024:.3f} MB, "
        f"{utilisation:.1%} of the cap, verdict {budget['verdict']}."
    )
    drift = budget.get("estimate_drift")
    if drift is not None and abs(drift) > 0.10:
        # Diagnostic, not a gate. The verdict already accounts for real bytes.
        print(f"  [note] {drift:+.0%} off the estimate, but measured size is what counts.")

    if budget["verdict"] == "over":
        return _fail(
            f"Pack is over budget at {utilisation:.1%}. Waze rejects oversized "
            "packs without saying so. Not staging."
        )
    if budget["verdict"] == "tight":
        print("  [warn] Above target but under the fail threshold. Staging anyway.")

    if code := stage(export_dir / "pack", args.uploader, args.name):
        return code

    print("\n  Next:")
    print(f"    cd {args.uploader}")
    print('    $env:PYTHONIOENCODING = "utf-8"')
    print(r"    .venv\Scripts\activate")
    print(r"    python mp3_upload\main.py")
    print("\n  Save both URLs it prints. The UUID cannot be recovered otherwise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
