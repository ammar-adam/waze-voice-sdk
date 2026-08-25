"""End-to-end pipeline test against real ffmpeg.

Builds synthetic source media, runs extract -> clean -> normalize -> validate ->
export -> QA render, and checks the audio that comes out. Skipped when ffmpeg is
not installed.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import fixtures

from waze_voice import config as config_module
from waze_voice import console, manifest as manifest_module, media, paths
from waze_voice.steps import clean, export, extract, normalize, qa, validate

HAVE_FFMPEG = media.find_tool("ffmpeg") is not None and media.find_tool("ffprobe") is not None


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg and ffprobe are required for pipeline tests")
class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        console.set_quiet(True)
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)

        cls.audio_root = root / "audio"
        cls.previous_env = os.environ.get(paths.AUDIO_ROOT_ENV)
        os.environ[paths.AUDIO_ROOT_ENV] = str(cls.audio_root)
        paths.ensure_dirs()

        cls.config = config_module.PipelineConfig()
        cls.phrases_path = fixtures.make_phrases_json(root / "phrases.json")
        cls.routes_path = fixtures.make_routes_json(root / "routes.json")
        cls.source_media = fixtures.make_source_media(root / "episode.wav", with_bed=True)
        cls.sources_path = fixtures.make_sources_csv(root / "sources.csv", cls.source_media)

        cls.extract_result = extract.run(
            config=cls.config,
            sources_path=cls.sources_path,
            phrases_path=cls.phrases_path,
        )
        cls.clean_result = clean.run(config=cls.config, mode="ffmpeg")
        cls.normalize_result = normalize.run(
            config=cls.config,
            phrases_path=cls.phrases_path,
            sources_path=cls.sources_path,
        )
        cls.export_result = export.run(
            config=cls.config,
            phrases_path=cls.phrases_path,
            allow_missing=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.previous_env is None:
            os.environ.pop(paths.AUDIO_ROOT_ENV, None)
        else:
            os.environ[paths.AUDIO_ROOT_ENV] = cls.previous_env
        console.set_quiet(False)
        cls.tmp.cleanup()

    # -- extract -----------------------------------------------------------

    def test_extract_cut_every_segment(self) -> None:
        self.assertEqual(len(self.extract_result.extracted), len(fixtures.SEGMENTS))
        self.assertTrue(self.extract_result.ok)

    def test_extract_durations_match_the_csv(self) -> None:
        for phrase_id, start, end, _ in fixtures.SEGMENTS:
            path = paths.extracted_dir() / f"{phrase_id}__take1.wav"
            self.assertTrue(path.is_file(), f"missing {path}")
            actual = media.duration_seconds(path)
            self.assertAlmostEqual(actual, end - start, delta=0.05)

    def test_extract_reports_phrase_with_no_source(self) -> None:
        self.assertIn("recalculating", self.extract_result.phrases_without_sources)

    def test_extract_is_idempotent(self) -> None:
        again = extract.run(
            config=self.config,
            sources_path=self.sources_path,
            phrases_path=self.phrases_path,
        )
        self.assertEqual(len(again.extracted), 0)
        self.assertEqual(len(again.skipped), len(fixtures.SEGMENTS))

    # -- clean -------------------------------------------------------------

    def test_clean_preserves_phrase_ids(self) -> None:
        """The scaffold's Demucs mode lost phrase IDs. Naming is checked here."""
        for phrase_id, _, _, _ in fixtures.SEGMENTS:
            self.assertTrue((paths.processed_dir() / f"{phrase_id}__take1.wav").is_file())
        self.assertTrue(self.clean_result.ok)

    # -- normalize ---------------------------------------------------------

    def test_all_sourced_phrases_normalized(self) -> None:
        self.assertEqual(len(self.normalize_result.normalized), len(fixtures.SEGMENTS))

    def test_missing_phrase_reported_not_invented(self) -> None:
        self.assertIn("recalculating", self.normalize_result.missing_required)

    def test_output_loudness_hits_the_target(self) -> None:
        """The point of the whole step: every clip lands at the same level."""
        target = self.config.loudness.target_lufs
        tolerance = self.config.loudness.tolerance_lu
        for clip in self.normalize_result.normalized:
            self.assertLessEqual(
                abs(clip.output_lufs - target),
                tolerance,
                f"{clip.phrase_id} landed at {clip.output_lufs} LUFS, target {target}",
            )

    def test_clips_end_up_within_1_lu_of_each_other(self) -> None:
        """Consistency between clips is the whole point, not just proximity to target."""
        levels = [clip.output_lufs for clip in self.normalize_result.normalized]
        self.assertLess(
            max(levels) - min(levels),
            1.0,
            f"spread across clips is too wide: {levels}",
        )

    def test_input_levels_actually_differed(self) -> None:
        """Guards the test itself: normalization must have had work to do."""
        inputs = [clip.input_lufs for clip in self.normalize_result.normalized]
        self.assertGreater(max(inputs) - min(inputs), 3.0, f"fixture too uniform: {inputs}")

    def test_true_peak_ceiling_respected(self) -> None:
        ceiling = self.config.loudness.true_peak_db
        for clip in self.normalize_result.normalized:
            self.assertLessEqual(clip.output_true_peak_db, ceiling + 0.5, clip.phrase_id)

    def test_master_files_are_mono_at_the_configured_rate(self) -> None:
        for clip in self.normalize_result.normalized:
            info = media.probe(clip.path)
            self.assertEqual(info.channels, self.config.audio.channels)
            self.assertEqual(info.sample_rate, self.config.audio.sample_rate)

    def test_manifest_records_provenance(self) -> None:
        built = manifest_module.Manifest.load()
        record = built.get("turn_left")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.origin, manifest_module.ORIGIN_EXTRACTED)
        self.assertEqual(record.source_path, str(self.source_media))
        self.assertIn("normalize", record.stages)
        self.assertIsNotNone(record.gain_applied_db)

    def test_phrase_status_updated_to_final(self) -> None:
        from waze_voice import phrases as phrases_module

        inventory = phrases_module.load(self.phrases_path)
        self.assertEqual(inventory.require("turn_left").status, "final")
        self.assertEqual(inventory.require("recalculating").status, "missing")

    # -- validate ----------------------------------------------------------

    def test_validate_flags_the_missing_required_clip(self) -> None:
        result = validate.run(
            config=self.config,
            phrases_path=self.phrases_path,
            sources_path=self.sources_path,
        )
        self.assertFalse(result.ok)
        self.assertEqual([p.id for p in result.missing_required], ["recalculating"])
        self.assertEqual(result.property_problems, [])
        self.assertEqual(result.loudness_problems, [])

    # -- export ------------------------------------------------------------

    def test_export_numbers_have_no_gaps(self) -> None:
        indexes = [clip.index for clip in self.export_result.exported]
        self.assertEqual(indexes, list(range(1, len(indexes) + 1)))

    def test_export_writes_checklist_and_verification_guide(self) -> None:
        export_dir = paths.export_dir()
        self.assertTrue((export_dir / export.CHECKLIST_NAME).is_file())
        self.assertTrue((export_dir / export.VERIFY_NAME).is_file())
        self.assertTrue((export_dir / export.MANIFEST_NAME).is_file())
        self.assertTrue((export_dir / export.README_NAME).is_file())

    def test_pack_manifest_marks_import_as_unverified(self) -> None:
        payload = json.loads(
            (paths.export_dir() / export.MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertFalse(payload["import_path_verified"])
        self.assertEqual(len(payload["clips"]), len(fixtures.SEGMENTS))
        self.assertIn("recalculating", [item["phrase_id"] for item in payload["missing"]])

    def test_checklist_lists_the_missing_prompt_for_manual_recording(self) -> None:
        text = (paths.export_dir() / export.CHECKLIST_NAME).read_text(encoding="utf-8")
        self.assertIn("Recalculating", text)
        self.assertIn("Not in this pack", text)

    def test_export_clips_are_copied(self) -> None:
        clips_dir = paths.export_dir() / export.CLIPS_DIRNAME
        copied = sorted(clips_dir.glob("*.mp3"))
        self.assertEqual(len(copied), len(fixtures.SEGMENTS))
        self.assertTrue(copied[0].name.startswith("001_"))

    # -- QA ----------------------------------------------------------------

    def test_qa_dry_run_reports_missing_before_playing(self) -> None:
        result = qa.run(
            config=self.config,
            phrases_path=self.phrases_path,
            routes_path=self.routes_path,
            master_dir=paths.master_dir(),
            dry_run=True,
        )
        self.assertEqual(result.missing, [])

    def test_qa_renders_a_route_of_the_expected_length(self) -> None:
        destination = paths.work_dir() / "route.wav"
        result = qa.run(
            config=self.config,
            phrases_path=self.phrases_path,
            routes_path=self.routes_path,
            master_dir=paths.master_dir(),
            render_to=destination,
        )
        self.assertIsNotNone(result.rendered)
        self.assertTrue(destination.is_file())

        clip_total = sum(
            media.duration_seconds(paths.master_dir() / f"{name}.mp3")
            for name in ("turn_left", "now", "turn_right", "arrived")
        )
        rendered = media.duration_seconds(destination)
        # Clips, plus two inter-step gaps, one intra-step gap, and the lead-in.
        self.assertGreater(rendered, clip_total)
        self.assertLess(rendered, clip_total + 5.0)


if __name__ == "__main__":
    unittest.main()
