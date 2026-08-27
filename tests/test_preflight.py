"""Pre-flight, and measured-versus-estimated size.

Pre-flight exists so nobody spends API calls on a pack that could never work.
Its job is to be honest about the difference between what it can check (schema,
filenames, clarity, arithmetic) and what only a real build can (duration, sound).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from waze_voice import config as config_module
from waze_voice import console, media, paths, preflight, presets, providers
from waze_voice.steps import export, synth

HAVE_FFMPEG = media.find_tool("ffmpeg") is not None and media.find_tool("ffprobe") is not None


def _mp3_bytes(seconds: float) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "c.mp3"
        media.run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=300:duration={seconds}:sample_rate=44100",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(out),
            ]
        )
        return out.read_bytes()


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        console.set_quiet(True)
        self.config = config_module.load()

    def tearDown(self) -> None:
        console.set_quiet(False)

    def test_passes_on_the_shipped_repository(self) -> None:
        report = preflight.run(config=self.config)
        self.assertTrue(report.ok, f"{report.inventory_problems} {report.filename_problems}")
        self.assertEqual(report.filename_problems, [])

    def test_reports_every_shipped_preset(self) -> None:
        report = preflight.run(config=self.config)
        names = {entry.name for entry in report.presets}
        self.assertEqual(names, {"eeyore", "pooh", "tigger"})

    def test_estimates_are_populated_and_plausible(self) -> None:
        report = preflight.run(config=self.config)
        for entry in report.presets:
            self.assertGreater(entry.estimated_seconds, 30, entry.name)
            self.assertGreater(entry.estimated_bytes, 0, entry.name)
            self.assertLessEqual(
                entry.utilisation,
                self.config.export.fail_above_utilisation,
                f"{entry.name} estimated over the fail threshold",
            )

    def test_a_single_preset_can_be_checked(self) -> None:
        report = preflight.run(config=self.config, only="eeyore")
        self.assertEqual([entry.name for entry in report.presets], ["eeyore"])

    def test_a_broken_preset_fails_preflight(self) -> None:
        broken = presets.presets_dir() / "preflight-broken.json"
        source = json.loads((presets.presets_dir() / "eeyore.json").read_text())
        source["lines"]["turn_left"] = "Go the leftover way."
        broken.write_text(json.dumps(source), encoding="utf-8")
        try:
            report = preflight.run(config=self.config, only="preflight-broken")
            self.assertFalse(report.ok)
            self.assertTrue(report.presets[0].errors)
        finally:
            broken.unlink()

    def test_filename_mapping_is_checked(self) -> None:
        """A phrase pointing at a filename Waze ignores must be caught here."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "phrases.json"
            data = json.loads((paths.config_dir() / "phrases.json").read_text())
            data["phrases"][0]["waze_filename"] = "TurnLeft.mp3"
            data["phrases"][1]["waze_filename"] = "TurnLeft.mp3"
            path.write_text(json.dumps(data), encoding="utf-8")
            # Duplicate slots make the inventory invalid, which preflight reports
            # rather than crashing on.
            report = preflight.run(config=self.config, phrases_path=path)
        self.assertFalse(report.ok)

    def test_no_api_key_is_not_a_failure(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            report = preflight.run(config=self.config)
        self.assertEqual(report.providers_ready, [])
        self.assertTrue(report.ok, "a missing key must not fail pre-flight")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required")
class MeasuredSizeTests(unittest.TestCase):
    """The build reports measured bytes; pre-flight reports an estimate."""

    def setUp(self) -> None:
        console.set_quiet(True)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous = os.environ.get(paths.AUDIO_ROOT_ENV)
        os.environ[paths.AUDIO_ROOT_ENV] = str(self.root / "audio")
        paths.ensure_dirs()
        self.config = config_module.load()

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop(paths.AUDIO_ROOT_ENV, None)
        else:
            os.environ[paths.AUDIO_ROOT_ENV] = self.previous
        console.set_quiet(False)
        self.tmp.cleanup()

    def _build(self, seconds: float, preset_name: str = "tigger"):
        from waze_voice import cli

        audio = _mp3_bytes(seconds)
        with (
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk"}, clear=False),
            mock.patch.object(providers, "_request", return_value=audio),
            mock.patch.object(synth, "check_consent", return_value=None),
        ):
            code = cli.main(
                ["quickstart", "--preset", preset_name, "--quiet"]
            )
        manifest = json.loads(
            (paths.export_dir() / export.MANIFEST_NAME).read_text(encoding="utf-8")
        )
        return code, manifest

    def test_reported_size_equals_bytes_on_disk(self) -> None:
        """Measured means measured: the manifest must match the filesystem."""
        _, manifest = self._build(1.1)
        pack_dir = paths.export_dir() / export.PACK_DIRNAME
        on_disk = sum(path.stat().st_size for path in pack_dir.glob("*.mp3"))
        self.assertEqual(on_disk, manifest["budget"]["total_bytes"])
        self.assertTrue(manifest["budget"]["measured"])

    def test_drift_is_reported_when_the_voice_is_slower_than_assumed(self) -> None:
        # 2.6 s clips against an estimate expecting roughly one second.
        _, manifest = self._build(2.6)
        drift = manifest["budget"]["estimate_drift"]
        self.assertIsNotNone(drift)
        assert drift is not None
        self.assertGreater(
            drift,
            presets.ESTIMATE_TOLERANCE,
            "a much slower voice should show up as positive drift",
        )

    def test_drift_is_small_when_the_estimate_is_close(self) -> None:
        inventory_seconds = presets.estimate_seconds("Turn left!", speed=1.0)
        _, manifest = self._build(inventory_seconds)
        drift = manifest["budget"]["estimate_drift"]
        self.assertIsNotNone(drift)
        assert drift is not None
        self.assertLess(abs(drift), 1.0, "estimate should be in the right ballpark")

    def test_build_stays_within_the_target_for_a_normal_voice(self) -> None:
        code, manifest = self._build(1.1)
        self.assertEqual(code, 0)
        self.assertEqual(manifest["budget"]["verdict"], "ok")
        self.assertLessEqual(
            manifest["budget"]["utilisation"], self.config.export.target_utilisation
        )

    def test_an_oversized_pack_fails_the_build(self) -> None:
        """Above the fail threshold the command must exit non-zero.

        The whole point of the threshold is that Waze will not tell you.
        """
        from waze_voice import cli

        audio = _mp3_bytes(1.1)
        tiny = config_module.load()
        with (
            mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk"}, clear=False),
            mock.patch.object(providers, "_request", return_value=audio),
            mock.patch.object(synth, "check_consent", return_value=None),
            mock.patch.object(
                config_module,
                "load",
                return_value=config_module.PipelineConfig(
                    audio=tiny.audio,
                    loudness=tiny.loudness,
                    trim=tiny.trim,
                    extract=tiny.extract,
                    clean=tiny.clean,
                    synth=tiny.synth,
                    # A cap so small that any real pack blows straight past it.
                    export=config_module.ExportConfig(budget_bytes=40_000),
                    qa=tiny.qa,
                ),
            ),
        ):
            code = cli.main(
                ["quickstart", "--preset", "eeyore", "--quiet"]
            )
        self.assertEqual(code, 1, "an oversized pack must not report success")


if __name__ == "__main__":
    unittest.main()
