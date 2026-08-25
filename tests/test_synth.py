"""Synthesis backend selection and the skip-it-entirely path.

Synthesis is the one step with a heavy optional dependency, so what happens when
it is *not* installed matters as much as what happens when it is. None of these
tests require a backend to be present.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fixtures

from waze_voice import config as config_module
from waze_voice import console, media, paths
from waze_voice.steps import synth

HAVE_FFMPEG = media.find_tool("ffmpeg") is not None and media.find_tool("ffprobe") is not None


class BackendAvailabilityTests(unittest.TestCase):
    def test_chatterbox_is_the_default(self) -> None:
        self.assertEqual(config_module.PipelineConfig().synth.backend, "chatterbox")
        self.assertEqual(config_module.load().synth.backend, "chatterbox")

    def test_unknown_backend_is_reported(self) -> None:
        available, reason = synth.is_available("telepathy")
        self.assertFalse(available)
        self.assertIn("telepathy", reason)

    def test_missing_chatterbox_gives_install_instructions(self) -> None:
        with mock.patch.object(synth, "_module_present", return_value=False):
            available, reason = synth.is_available("chatterbox")
        self.assertFalse(available)
        self.assertIn("requirements-tts.txt", reason)

    def test_missing_coqui_names_the_right_package(self) -> None:
        """The archived `TTS` package and the maintained `coqui-tts` fork differ."""
        with mock.patch.object(synth, "_module_present", return_value=False):
            available, reason = synth.is_available("xtts")
        self.assertFalse(available)
        self.assertIn("coqui-tts", reason)

    def test_available_when_modules_present(self) -> None:
        with mock.patch.object(synth, "_module_present", return_value=True):
            self.assertEqual(synth.is_available("chatterbox"), (True, ""))
            self.assertEqual(synth.is_available("xtts"), (True, ""))

    def test_load_backend_rejects_unknown(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            synth.load_backend(config_module.PipelineConfig(), "telepathy")
        self.assertIn("telepathy", str(caught.exception))


class ConsentGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_gate_blocks_without_acknowledgement(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            synth.check_consent(accepted=False, repo_root=self.root)
        self.assertIn("--accept-voice-terms", str(caught.exception))

    def test_receipt_is_written_once_and_then_honoured(self) -> None:
        synth.check_consent(accepted=True, repo_root=self.root)
        receipt = self.root / synth.CONSENT_RECEIPT
        self.assertTrue(receipt.is_file())
        # A later run without the flag passes because the receipt exists.
        synth.check_consent(accepted=False, repo_root=self.root)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required")
class DegradationTests(unittest.TestCase):
    """The pipeline must stay useful with no synthesis backend installed."""

    def setUp(self) -> None:
        console.set_quiet(True)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous = os.environ.get(paths.AUDIO_ROOT_ENV)
        os.environ[paths.AUDIO_ROOT_ENV] = str(self.root / "audio")
        paths.ensure_dirs()

        self.config = config_module.PipelineConfig()
        self.phrases_path = fixtures.make_phrases_json(self.root / "phrases.json")
        source = fixtures.make_source_media(self.root / "episode.wav")
        self.sources_path = fixtures.make_sources_csv(self.root / "sources.csv", source)

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop(paths.AUDIO_ROOT_ENV, None)
        else:
            os.environ[paths.AUDIO_ROOT_ENV] = self.previous
        console.set_quiet(False)
        self.tmp.cleanup()

    def test_dry_run_lists_gaps_without_a_backend(self) -> None:
        with mock.patch.object(synth, "_module_present", return_value=False):
            result = synth.run(
                config=self.config,
                phrases_path=self.phrases_path,
                dry_run=True,
            )
        # recalculating is the fixture phrase with no source row.
        self.assertIn("recalculating", result.gaps)
        self.assertEqual(result.synthesized, [])

    def test_missing_backend_exits_with_guidance_not_a_traceback(self) -> None:
        with mock.patch.object(synth, "_module_present", return_value=False):
            with self.assertRaises(SystemExit) as caught:
                synth.run(
                    config=self.config,
                    phrases_path=self.phrases_path,
                    accept_voice_terms=True,
                )
        message = str(caught.exception)
        self.assertIn("not installed", message)
        self.assertIn("requirements-tts.txt", message)

    def test_full_run_completes_and_exports_without_a_backend(self) -> None:
        """The headline degradation guarantee, end to end."""
        from waze_voice import cli
        from waze_voice.steps import export

        with mock.patch.object(synth, "_module_present", return_value=False):
            code = cli.main(
                [
                    "run",
                    "--sources",
                    str(self.sources_path),
                    "--phrases",
                    str(self.phrases_path),
                    "--allow-missing",
                    "--quiet",
                ]
            )

        self.assertEqual(code, 0, "a missing synthesis backend must not fail the run")

        export_dir = paths.export_dir()
        self.assertTrue((export_dir / export.CHECKLIST_NAME).is_file())
        clips = list((export_dir / export.CLIPS_DIRNAME).glob("*.mp3"))
        self.assertEqual(len(clips), len(fixtures.SEGMENTS))

        # The phrase synthesis would have filled is handed to the user instead.
        checklist = (export_dir / export.CHECKLIST_NAME).read_text(encoding="utf-8")
        self.assertIn("Not in this pack", checklist)
        self.assertIn("Recalculating", checklist)

    def test_no_tts_flag_skips_without_probing(self) -> None:
        from waze_voice import cli

        with mock.patch.object(synth, "is_available") as probe:
            code = cli.main(
                [
                    "run",
                    "--sources",
                    str(self.sources_path),
                    "--phrases",
                    str(self.phrases_path),
                    "--no-tts",
                    "--allow-missing",
                    "--quiet",
                ]
            )
        self.assertEqual(code, 0)
        probe.assert_not_called()


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required")
class ReferenceAudioTests(unittest.TestCase):
    def setUp(self) -> None:
        console.set_quiet(True)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.processed = self.root / "processed"
        self.processed.mkdir()

    def tearDown(self) -> None:
        console.set_quiet(False)
        self.tmp.cleanup()

    def test_reference_is_one_continuous_file_of_the_longest_clips(self) -> None:
        for index, seconds in enumerate((1.0, 3.0, 2.0), start=1):
            media.run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={200 + index * 60}:duration={seconds}:sample_rate=44100",
                    "-ac",
                    "1",
                    str(self.processed / f"clip{index}.wav"),
                ]
            )

        destination = self.root / "reference.wav"
        synth.build_reference(
            config=config_module.PipelineConfig(),
            source_dir=self.processed,
            destination=destination,
        )

        self.assertTrue(destination.is_file())
        # 6 s of clips plus the inter-clip gaps, in one file.
        self.assertGreater(media.duration_seconds(destination), 6.0)

    def test_missing_clips_gives_an_actionable_error(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            synth.build_reference(
                config=config_module.PipelineConfig(),
                source_dir=self.processed,
                destination=self.root / "reference.wav",
            )
        self.assertIn("extract and clean", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
