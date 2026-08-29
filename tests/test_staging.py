"""The gates between a finished build and an upload nobody can take back.

Waze rejects a bad pack silently and the community uploader publishes an
incomplete one without complaining, so everything worth catching has to be
caught before the bytes leave this machine. These are the last checks that run.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
for entry in (str(ROOT), str(ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import build_all  # noqa: E402
import stage_for_upload  # noqa: E402

from waze_voice import wazepack  # noqa: E402


def _pack(directory: Path, filenames: set[str]) -> Path:
    pack = directory / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (pack / name).write_bytes(b"ID3" + b"\x00" * 64)
    return pack


class StageGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.uploader = self.root / "uploader"
        (self.uploader / "mp3_upload" / "input_packs").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_complete_pack_is_staged_under_the_voice_name(self) -> None:
        pack = _pack(self.root, set(wazepack.VALID_FILENAMES))
        code = stage_for_upload.stage(pack, self.uploader, "Winnie the Pooh")
        self.assertEqual(code, 0)
        staged = self.uploader / "mp3_upload" / "input_packs" / "Winnie the Pooh"
        self.assertEqual(len(list(staged.glob("*.mp3"))), 43)

    def test_a_single_unit_pack_is_accepted(self) -> None:
        """39 files is a complete metric pack, not a broken 43-file one.

        Counting files rejected this; checking names does not.
        """
        metric = {slot.filename for slot in wazepack.slots_for_units(wazepack.UNITS_METRIC)}
        pack = _pack(self.root, metric)
        self.assertLess(len(metric), len(wazepack.VALID_FILENAMES))
        code = stage_for_upload.stage(pack, self.uploader, "Metric Only")
        self.assertEqual(code, 0, "a metric-only pack is a supported build")

    def test_a_misnamed_file_is_refused(self) -> None:
        """43 files, one of them named something Waze ignores. A count passes
        this; it is also the case that actually costs an upload."""
        names = set(wazepack.VALID_FILENAMES)
        names.remove(sorted(names)[0])
        names.add("TurnLeftt.mp3")
        pack = _pack(self.root, names)
        self.assertEqual(len(names), 43)
        code = stage_for_upload.stage(pack, self.uploader, "Typo")
        self.assertEqual(code, 1)
        self.assertFalse((self.uploader / "mp3_upload" / "input_packs" / "Typo").exists())

    def test_a_pack_missing_core_prompts_is_refused(self) -> None:
        names = set(wazepack.VALID_FILENAMES) - wazepack.core_filenames()
        pack = _pack(self.root, names)
        self.assertEqual(stage_for_upload.stage(pack, self.uploader, "Hollow"), 1)

    def test_an_empty_directory_is_refused(self) -> None:
        pack = _pack(self.root, set())
        self.assertEqual(stage_for_upload.stage(pack, self.uploader, "Empty"), 1)

    def test_restaging_replaces_rather_than_merges(self) -> None:
        """Otherwise a file from a previous character survives into this pack."""
        staged = self.uploader / "mp3_upload" / "input_packs" / "Reused"
        staged.mkdir(parents=True)
        (staged / "TurnLeft.mp3").write_bytes(b"stale")
        (staged / "NotAWazeFile.mp3").write_bytes(b"stale")

        pack = _pack(self.root, set(wazepack.VALID_FILENAMES))
        self.assertEqual(stage_for_upload.stage(pack, self.uploader, "Reused"), 0)
        self.assertFalse((staged / "NotAWazeFile.mp3").exists())
        self.assertEqual(len(list(staged.glob("*.mp3"))), 43)


class BuildCommandTests(unittest.TestCase):
    def _command(self, **kwargs) -> list[str]:
        with mock.patch.object(stage_for_upload.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            stage_for_upload.build("pooh", "pooh", **kwargs)
        return run.call_args[0][0]

    def test_consent_is_always_passed(self) -> None:
        """Without it the first build on a clean clone exits instead of building."""
        self.assertIn("--accept-voice-terms", self._command())

    def test_no_overrides_leaves_the_preset_alone(self) -> None:
        command = self._command()
        self.assertNotIn("--provider", command)
        self.assertNotIn("--voice", command)

    def test_overrides_are_forwarded(self) -> None:
        command = self._command(provider="fish", voice="abc123")
        self.assertIn("--provider", command)
        self.assertEqual(command[command.index("--provider") + 1], "fish")
        self.assertEqual(command[command.index("--voice") + 1], "abc123")


class PlaceholderKeyTests(unittest.TestCase):
    """A README placeholder is 'present' and then fails as a 401 mid-build."""

    def _results(self, env: dict[str, str]) -> dict[str, str]:
        with (
            mock.patch.dict(os.environ, env, clear=False),
            mock.patch.object(build_all, "build", return_value=0) as build,
            mock.patch.object(build_all, "stage", return_value=0),
            mock.patch.object(build_all.console, "table") as table,
            mock.patch.object(build_all.packs, "exists", return_value=True),
        ):
            build_all.main(["--only", "pooh", "--no-stage"])
            self.built = build.called
        return dict(table.call_args[0][0])

    def test_a_placeholder_key_is_skipped_not_built(self) -> None:
        results = self._results({"OPENAI_API_KEY": "sk-..."})
        self.assertIn("placeholder", results["pooh"])
        self.assertFalse(self.built, "no request should be made with a placeholder")

    def test_a_plausible_key_builds(self) -> None:
        results = self._results({"OPENAI_API_KEY": "sk-proj-" + "a" * 40})
        self.assertEqual(results["pooh"], "built")
        self.assertTrue(self.built)

    def test_an_absent_key_is_reported_as_missing_not_broken(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            results = self._results({})
        self.assertIn("OPENAI_API_KEY", results["pooh"])


class FishRoutingTests(unittest.TestCase):
    def test_every_character_has_a_waze_facing_name(self) -> None:
        """The folder name is what the driver sees, so it is not the slug."""
        for preset, name in build_all.CHARACTERS.items():
            with self.subTest(preset=preset):
                self.assertTrue(name)
                self.assertNotEqual(name, preset)

    def test_fish_overrides_name_real_model_ids(self) -> None:
        for preset, voice in build_all.FISH_VOICES.items():
            with self.subTest(preset=preset):
                self.assertIn(preset, build_all.CHARACTERS)
                self.assertRegex(voice, r"^[0-9a-f]{32}$")

    def test_fish_routing_covers_the_catalogue_voice_presets(self) -> None:
        """--fish exists so one key covers the whole run. If a preset using a
        catalogue voice has no override, that promise quietly breaks."""
        from waze_voice import presets

        for preset in build_all.CHARACTERS:
            if presets.load(preset).provider != "fish":
                self.assertIn(preset, build_all.FISH_VOICES, preset)


if __name__ == "__main__":
    unittest.main()
