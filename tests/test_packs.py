"""Multiple voice packs from one clone.

Two packs must not be able to see each other's clips. A pack name must not be
able to escape ``packs/``, because the export step deletes recursively inside
whatever directory it is handed.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fixtures

from waze_voice import config as config_module
from waze_voice import console, media, packs, paths

HAVE_FFMPEG = media.find_tool("ffmpeg") is not None and media.find_tool("ffprobe") is not None


class PackNameTests(unittest.TestCase):
    """Names become directory names, so the validation is a security boundary."""

    def test_traversal_is_rejected(self) -> None:
        for name in ("..", "../evil", "a/b", "a\\b", "/etc", "C:\\Windows", "."):
            with self.subTest(name=name), self.assertRaises(SystemExit):
                paths.validate_pack_name(name)

    def test_empty_and_hidden_are_rejected(self) -> None:
        for name in ("", "   ", ".hidden", "-leading"):
            with self.subTest(name=name), self.assertRaises(SystemExit):
                paths.validate_pack_name(name)

    def test_reasonable_names_are_accepted(self) -> None:
        for name in ("narrator", "narrator-a", "voice_2", "v1.2", "A"):
            with self.subTest(name=name):
                self.assertEqual(paths.validate_pack_name(name), name)

    def test_overlong_name_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            paths.validate_pack_name("x" * 200)

    def test_a_valid_name_stays_inside_packs(self) -> None:
        root = paths.pack_root("narrator-a").resolve()
        self.assertEqual(root.parent, paths.packs_dir().resolve())


class PackLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        console.set_quiet(True)
        self.tmp = tempfile.TemporaryDirectory()
        self.packs_dir = Path(self.tmp.name) / "packs"
        self.packs_dir.mkdir()
        # Keep the real packs/ directory out of the tests.
        self.patcher = mock.patch.object(paths, "packs_dir", return_value=self.packs_dir)
        self.patcher.start()
        paths.set_active_pack(None)

    def tearDown(self) -> None:
        self.patcher.stop()
        paths.set_active_pack(None)
        console.set_quiet(False)
        self.tmp.cleanup()

    def test_create_builds_the_layout(self) -> None:
        pack = packs.create("narrator", label="Narrator", voice="my own recordings")
        self.assertTrue(pack.config_path.is_file())
        self.assertTrue(pack.sources_path.is_file())
        for name in ("extracted", "processed", "synthesized", "master", "export"):
            self.assertTrue((pack.audio_root / name).is_dir(), name)

    def test_starter_csv_has_the_real_header(self) -> None:
        """An empty file gives a worse error than one that shows the format."""
        pack = packs.create("narrator")
        header = pack.sources_path.read_text(encoding="utf-8").strip()
        self.assertIn("phrase_id", header)
        self.assertIn("source_path", header)

    def test_metadata_round_trips(self) -> None:
        packs.create("narrator", label="Narrator", voice="podcast", notes="take 2")
        loaded = packs.load("narrator")
        self.assertEqual(loaded.label, "Narrator")
        self.assertEqual(loaded.voice, "podcast")
        self.assertEqual(loaded.notes, "take 2")
        self.assertTrue(loaded.created_at)

    def test_creating_twice_is_refused(self) -> None:
        packs.create("narrator")
        with self.assertRaises(SystemExit):
            packs.create("narrator")

    def test_loading_a_missing_pack_lists_the_real_ones(self) -> None:
        packs.create("narrator-a")
        packs.create("narrator-b")
        with self.assertRaises(SystemExit) as caught:
            packs.load("narrator-c")
        message = str(caught.exception)
        self.assertIn("narrator-a", message)
        self.assertIn("narrator-b", message)

    def test_list_skips_directories_without_config(self) -> None:
        packs.create("real")
        (self.packs_dir / "just-a-folder").mkdir()
        self.assertEqual([p.name for p in packs.list_packs()], ["real"])

    def test_list_survives_a_corrupt_config(self) -> None:
        packs.create("good")
        broken = self.packs_dir / "broken"
        broken.mkdir()
        (broken / packs.PACK_CONFIG_NAME).write_text("{not json", encoding="utf-8")
        self.assertEqual([p.name for p in packs.list_packs()], ["good"])

    def test_overrides_are_reported(self) -> None:
        plain = packs.create("plain")
        self.assertEqual(plain.overrides, [])
        custom = packs.create("custom", copy_phrases=True, copy_routes=True)
        self.assertEqual(sorted(custom.overrides), ["phrases.json", "routes.json"])


class PackPathResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        console.set_quiet(True)
        self.tmp = tempfile.TemporaryDirectory()
        self.packs_dir = Path(self.tmp.name) / "packs"
        self.packs_dir.mkdir()
        self.patcher = mock.patch.object(paths, "packs_dir", return_value=self.packs_dir)
        self.patcher.start()
        self.previous_env = os.environ.pop(paths.AUDIO_ROOT_ENV, None)
        paths.set_active_pack(None)

    def tearDown(self) -> None:
        self.patcher.stop()
        paths.set_active_pack(None)
        if self.previous_env is not None:
            os.environ[paths.AUDIO_ROOT_ENV] = self.previous_env
        else:
            os.environ.pop(paths.AUDIO_ROOT_ENV, None)
        console.set_quiet(False)
        self.tmp.cleanup()

    def test_no_pack_uses_the_shared_tree(self) -> None:
        self.assertEqual(paths.audio_root(), paths.repo_root() / "audio")

    def test_pack_redirects_the_whole_audio_tree(self) -> None:
        packs.create("narrator")
        paths.set_active_pack("narrator")
        expected = self.packs_dir / "narrator" / "audio"
        self.assertEqual(paths.audio_root(), expected)
        self.assertEqual(paths.master_dir(), expected / "master")
        self.assertEqual(paths.manifest_path().parent, expected)
        self.assertEqual(paths.qa_report_path().parent, expected)

    def test_explicit_audio_root_beats_the_pack(self) -> None:
        """A test or a one-off should be able to redirect without touching packs."""
        packs.create("narrator")
        paths.set_active_pack("narrator")
        override = Path(self.tmp.name) / "elsewhere"
        os.environ[paths.AUDIO_ROOT_ENV] = str(override)
        self.assertEqual(paths.audio_root(), override.resolve())

    def test_phrases_fall_back_to_shared_config(self) -> None:
        packs.create("narrator")
        paths.set_active_pack("narrator")
        self.assertEqual(paths.phrases_path(), paths.config_dir() / "phrases.json")

    def test_phrases_override_is_used_when_present(self) -> None:
        pack = packs.create("narrator", copy_phrases=True)
        paths.set_active_pack("narrator")
        self.assertEqual(paths.phrases_path(), pack.phrases_path)

    def test_sources_come_from_the_pack(self) -> None:
        pack = packs.create("narrator")
        paths.set_active_pack("narrator")
        self.assertEqual(paths.sources_path(), pack.sources_path)

    def test_env_var_selects_a_pack(self) -> None:
        packs.create("narrator")
        paths.set_active_pack(None)
        os.environ[paths.PACK_ENV] = "narrator"
        try:
            self.assertEqual(paths.active_pack(), "narrator")
        finally:
            os.environ.pop(paths.PACK_ENV, None)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required")
class TwoPacksAreIsolatedTests(unittest.TestCase):
    """The headline guarantee: two voices, one clone, no crosstalk."""

    @classmethod
    def setUpClass(cls) -> None:
        console.set_quiet(True)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.packs_dir = Path(cls.tmp.name) / "packs"
        cls.packs_dir.mkdir()
        cls.patcher = mock.patch.object(paths, "packs_dir", return_value=cls.packs_dir)
        cls.patcher.start()
        cls.previous_env = os.environ.pop(paths.AUDIO_ROOT_ENV, None)

        cls.config = config_module.PipelineConfig()
        cls.phrases_path = fixtures.make_phrases_json(Path(cls.tmp.name) / "phrases.json")

        from waze_voice.steps import clean, export, extract, normalize

        cls.results = {}
        # Two packs, two source recordings, pitched apart so the finished clips
        # cannot be confused for one another.
        for name, pitch in (("voice-a", 1.0), ("voice-b", 1.6)):
            pack = packs.create(name, label=name)
            paths.set_active_pack(name)
            paths.ensure_dirs()

            source = fixtures.make_source_media(
                pack.root / "media" / "episode.wav", with_bed=True, pitch=pitch
            )
            fixtures.make_sources_csv(pack.sources_path, source)

            extract.run(
                config=cls.config,
                sources_path=pack.sources_path,
                phrases_path=cls.phrases_path,
            )
            clean.run(config=cls.config, mode="ffmpeg")
            normalize.run(
                config=cls.config,
                phrases_path=cls.phrases_path,
                sources_path=pack.sources_path,
            )
            cls.results[name] = export.run(
                config=cls.config, phrases_path=cls.phrases_path, allow_missing=True
            )
        paths.set_active_pack(None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.patcher.stop()
        paths.set_active_pack(None)
        if cls.previous_env is not None:
            os.environ[paths.AUDIO_ROOT_ENV] = cls.previous_env
        console.set_quiet(False)
        cls.tmp.cleanup()

    def _pack_files(self, name: str) -> dict[str, Path]:
        pack_dir = packs.load(name).export_dir / "pack"
        return {path.name: path for path in pack_dir.glob("*.mp3")}

    def test_both_packs_built(self) -> None:
        for name in ("voice-a", "voice-b"):
            self.assertTrue(self.results[name].files, f"{name} produced nothing")

    def test_each_pack_has_its_own_audio_tree(self) -> None:
        a, b = packs.load("voice-a"), packs.load("voice-b")
        self.assertNotEqual(a.audio_root, b.audio_root)
        self.assertTrue(a.master_count() > 0 and b.master_count() > 0)

    def test_waze_filenames_match_but_the_audio_does_not(self) -> None:
        """Waze needs the same filenames in every pack; the bytes must differ."""
        a, b = self._pack_files("voice-a"), self._pack_files("voice-b")
        self.assertEqual(set(a), set(b), "both packs should fill the same Waze slots")
        self.assertTrue(a, "no clips were exported")
        for name in a:
            self.assertNotEqual(
                a[name].read_bytes(),
                b[name].read_bytes(),
                f"{name} is byte-identical across two different voices",
            )

    def test_manifests_are_separate(self) -> None:
        a, b = packs.load("voice-a"), packs.load("voice-b")
        self.assertNotEqual(
            (a.export_dir / "pack-manifest.json").resolve(),
            (b.export_dir / "pack-manifest.json").resolve(),
        )
        self.assertTrue((a.export_dir / "pack-manifest.json").is_file())
        self.assertTrue((b.export_dir / "pack-manifest.json").is_file())

    def test_build_manifests_do_not_leak_between_packs(self) -> None:
        from waze_voice import manifest as manifest_module

        paths.set_active_pack("voice-a")
        try:
            a_manifest = manifest_module.Manifest.load()
            a_source = a_manifest.record("turn_left").source_path
        finally:
            paths.set_active_pack(None)

        paths.set_active_pack("voice-b")
        try:
            b_manifest = manifest_module.Manifest.load()
            b_source = b_manifest.record("turn_left").source_path
        finally:
            paths.set_active_pack(None)

        self.assertTrue(a_source and b_source)
        self.assertNotEqual(a_source, b_source, "both packs recorded the same source media")


if __name__ == "__main__":
    unittest.main()
