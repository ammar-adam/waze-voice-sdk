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
from waze_voice import console, media, paths, wazepack
from waze_voice import manifest as manifest_module
from waze_voice.steps import clean, export, extract, normalize, qa, validate

HAVE_FFMPEG = media.find_tool("ffmpeg") is not None and media.find_tool("ffprobe") is not None

MISSING_ID = fixtures.MISSING_PHRASE[0]
MISSING_WAZE = fixtures.MISSING_PHRASE[1]


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
        for phrase_id, _, _, _, start, end, _ in fixtures.SEGMENTS:
            path = paths.extracted_dir() / f"{phrase_id}__take1.wav"
            self.assertTrue(path.is_file(), f"missing {path}")
            actual = media.duration_seconds(path)
            self.assertAlmostEqual(actual, end - start, delta=0.05)

    def test_extract_reports_phrase_with_no_source(self) -> None:
        self.assertIn(MISSING_ID, self.extract_result.phrases_without_sources)

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
        for phrase_id, _, _, _, _, _, _ in fixtures.SEGMENTS:
            self.assertTrue((paths.processed_dir() / f"{phrase_id}__take1.wav").is_file())
        self.assertTrue(self.clean_result.ok)

    # -- normalize ---------------------------------------------------------

    def test_all_sourced_phrases_normalized(self) -> None:
        self.assertEqual(len(self.normalize_result.normalized), len(fixtures.SEGMENTS))

    def test_missing_phrase_reported_not_invented(self) -> None:
        self.assertIn(MISSING_ID, self.normalize_result.missing_required)

    def test_output_loudness_hits_the_target(self) -> None:
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
        self.assertEqual(inventory.require(MISSING_ID).status, "missing")

    # -- validate ----------------------------------------------------------

    def test_validate_flags_the_missing_required_clip(self) -> None:
        result = validate.run(
            config=self.config,
            phrases_path=self.phrases_path,
            sources_path=self.sources_path,
        )
        self.assertFalse(result.ok)
        self.assertEqual([p.id for p in result.missing_required], [MISSING_ID])
        self.assertEqual(result.property_problems, [])
        self.assertEqual(result.loudness_problems, [])

    def test_validate_estimates_the_pack_against_the_budget(self) -> None:
        result = validate.run(
            config=self.config,
            phrases_path=self.phrases_path,
            sources_path=self.sources_path,
        )
        self.assertGreater(result.estimated_pack_bytes, 0)
        self.assertEqual(result.budget_bytes, self.config.export.budget_bytes)
        self.assertFalse(result.over_budget)

    def test_validate_reports_waze_slots_nobody_claims(self) -> None:
        """The fixture covers 9 of Waze's 43 slots; the rest should be named."""
        result = validate.run(
            config=self.config,
            phrases_path=self.phrases_path,
            sources_path=self.sources_path,
        )
        self.assertIn("TickerPoints.mp3", result.unclaimed_slots)
        self.assertNotIn("TurnLeft.mp3", result.unclaimed_slots)

    # -- export ------------------------------------------------------------

    def test_pack_uses_waze_filenames(self) -> None:
        pack_dir = paths.export_dir() / export.PACK_DIRNAME
        written = {path.name for path in pack_dir.glob("*.mp3")}
        self.assertTrue(written, "no pack files written")
        self.assertTrue(
            written <= wazepack.VALID_FILENAMES,
            f"pack contains names Waze does not recognise: {written - wazepack.VALID_FILENAMES}",
        )
        self.assertIn("TurnLeft.mp3", written)
        self.assertIn("400.mp3", written)
        self.assertIn("400meters.mp3", written)

    def test_pack_carries_both_unit_systems(self) -> None:
        written = {path.name for path in (paths.export_dir() / export.PACK_DIRNAME).glob("*.mp3")}
        metric = {s.filename for s in wazepack.SLOTS if s.units == wazepack.UNITS_METRIC}
        imperial = {s.filename for s in wazepack.SLOTS if s.units == wazepack.UNITS_IMPERIAL}
        self.assertTrue(written & metric, "no metric distance callout in the pack")
        self.assertTrue(written & imperial, "no imperial distance callout in the pack")

    def test_pack_fits_the_budget(self) -> None:
        self.assertIsNotNone(self.export_result.plan)
        self.assertFalse(self.export_result.over_budget)
        self.assertLessEqual(
            self.export_result.total_bytes, self.config.export.budget_bytes
        )

    def test_reported_size_matches_bytes_on_disk(self) -> None:
        """The number in the report has to be the number Waze will see."""
        pack_dir = paths.export_dir() / export.PACK_DIRNAME
        on_disk = sum(path.stat().st_size for path in pack_dir.glob("*.mp3"))
        self.assertEqual(on_disk, self.export_result.total_bytes)

    def test_long_low_priority_clip_gets_fewer_bits(self) -> None:
        """The whole point of the weighted strategy."""
        plan = self.export_result.plan
        assert plan is not None
        greeting = plan.get("StartDrive1.mp3")  # 4.0s, weight 1.0
        turn = plan.get("TurnLeft.mp3")  # 1.1s, weight 3.0
        assert greeting is not None and turn is not None
        self.assertLessEqual(
            greeting.bitrate_kbps,
            turn.bitrate_kbps,
            "a long, rarely heard clip should not outrank a short, frequent one",
        )

    def test_synthesized_clips_are_labelled_from_the_manifest(self) -> None:
        """Normalization rewrites every status to "final".

        So the inventory can no longer distinguish a synthesized clip from a cut
        one by export time, and reading `phrase.status` here silently labelled
        every synthetic prompt as source media. Provenance comes from the build
        manifest instead.
        """
        built = manifest_module.Manifest.load()
        record = built.record("arrived")
        original_origin = record.origin
        record.origin = manifest_module.ORIGIN_SYNTHESIZED
        built.save()
        try:
            target = self.audio_root / "export-origin"
            result = export.run(
                config=self.config,
                phrases_path=self.phrases_path,
                export_dir=target,
                allow_missing=True,
            )
            arrived = next(item for item in result.files if item.phrase.id == "arrived")
            self.assertTrue(arrived.is_synthesized)
            self.assertEqual(arrived.origin_label, "synthesized")

            turn = next(item for item in result.files if item.phrase.id == "turn_left")
            self.assertFalse(turn.is_synthesized)
            self.assertEqual(turn.origin_label, "source media")

            checklist = (target / export.CHECKLIST_NAME).read_text(encoding="utf-8")
            self.assertIn("## Synthesized prompts", checklist)
        finally:
            # Restore on the same instance that gets saved; other tests in this
            # class share the manifest.
            restored = manifest_module.Manifest.load()
            restored.record("arrived").origin = original_origin
            restored.save()

    def test_export_writes_the_upload_paperwork(self) -> None:
        export_dir = paths.export_dir()
        self.assertTrue((export_dir / export.CHECKLIST_NAME).is_file())
        self.assertTrue((export_dir / export.GUIDE_NAME).is_file())
        self.assertTrue((export_dir / export.MANIFEST_NAME).is_file())
        self.assertTrue((export_dir / export.README_NAME).is_file())

    def test_guide_documents_the_confirmed_upload_method(self) -> None:
        text = (paths.export_dir() / export.GUIDE_NAME).read_text(encoding="utf-8")
        self.assertIn("waze.com/ul?acvp=", text)
        self.assertIn("voice-prompts-ipv6.waze.com", text)
        self.assertIn("0.8 MB", text)

    def test_pack_manifest_reports_the_budget(self) -> None:
        payload = json.loads(
            (paths.export_dir() / export.MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertTrue(payload["budget"]["within_budget"])
        self.assertEqual(payload["budget"]["limit_bytes"], self.config.export.budget_bytes)
        self.assertEqual(len(payload["clips"]), len(fixtures.SEGMENTS))
        names = {clip["waze_filename"] for clip in payload["clips"]}
        self.assertTrue(names <= wazepack.VALID_FILENAMES)
        self.assertIn(MISSING_WAZE, [item["waze_filename"] for item in payload["missing"]])

    def test_checklist_lists_the_missing_prompt(self) -> None:
        text = (paths.export_dir() / export.CHECKLIST_NAME).read_text(encoding="utf-8")
        self.assertIn(MISSING_WAZE, text)
        self.assertIn("Size budget", text)

    def test_single_unit_export_drops_the_other_set(self) -> None:
        target = self.audio_root / "export-metric"
        result = export.run(
            config=self.config,
            phrases_path=self.phrases_path,
            export_dir=target,
            units="metric",
            allow_missing=True,
        )
        written = {path.name for path in (target / export.PACK_DIRNAME).glob("*.mp3")}
        self.assertIn("400meters.mp3", written)
        self.assertNotIn("400.mp3", written)
        self.assertEqual(result.units, "metric")

    def test_uniform_strategy_still_available(self) -> None:
        target = self.audio_root / "export-uniform"
        result = export.run(
            config=self.config,
            phrases_path=self.phrases_path,
            export_dir=target,
            strategy="uniform",
            allow_missing=True,
        )
        plan = result.plan
        assert plan is not None
        rates = {item.bitrate_kbps for item in plan.allocations}
        self.assertEqual(len(rates), 1, f"uniform strategy used several bitrates: {rates}")

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
            for name in ("turn_left", "in_quarter_mile", "turn_right", "arrived")
        )
        rendered = media.duration_seconds(destination)
        self.assertGreater(rendered, clip_total)
        self.assertLess(rendered, clip_total + 5.0)


if __name__ == "__main__":
    unittest.main()
