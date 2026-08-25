"""Phrase inventory, source CSV, route, and take-resolution tests.

No ffmpeg needed. These cover the parsing and selection logic where a silent
wrong answer would ship a broken voice pack.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from waze_voice import phrases, routes, sources, takes


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


class PhraseInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_inventory_loads(self) -> None:
        inventory = phrases.load(strict=True)
        self.assertGreater(len(inventory), 0)
        self.assertTrue(all(phrase.filename.endswith(".mp3") for phrase in inventory))

    def test_duplicate_ids_reported(self) -> None:
        entry = {
            "id": "turn_left",
            "label": "Turn left",
            "required": True,
            "filename": "turn_left.mp3",
            "status": "missing",
        }
        second = dict(entry, filename="other.mp3")
        _, errors = phrases.validate_raw({"phrases": [entry, second]})
        self.assertTrue(any("Duplicate phrase id" in error for error in errors))

    def test_filename_must_not_be_a_path(self) -> None:
        entry = {
            "id": "turn_left",
            "label": "Turn left",
            "required": True,
            "filename": "sub/turn_left.mp3",
            "status": "missing",
        }
        _, errors = phrases.validate_raw({"phrases": [entry]})
        self.assertTrue(any("bare filename" in error for error in errors))

    def test_unknown_status_and_group_rejected(self) -> None:
        entry = {
            "id": "turn_left",
            "label": "Turn left",
            "required": True,
            "filename": "turn_left.mp3",
            "status": "nearly",
            "group": "nowhere",
        }
        _, errors = phrases.validate_raw({"phrases": [entry]})
        self.assertTrue(any("status" in error for error in errors))
        self.assertTrue(any("group" in error for error in errors))

    def test_export_order_follows_group_then_order(self) -> None:
        payload = {
            "phrases": [
                {
                    "id": "alert_one",
                    "label": "Alert",
                    "required": False,
                    "filename": "a.mp3",
                    "status": "missing",
                    "group": "alert",
                    "order": 1,
                },
                {
                    "id": "man_two",
                    "label": "Second maneuver",
                    "required": True,
                    "filename": "b.mp3",
                    "status": "missing",
                    "group": "maneuver",
                    "order": 2,
                },
                {
                    "id": "man_one",
                    "label": "First maneuver",
                    "required": True,
                    "filename": "c.mp3",
                    "status": "missing",
                    "group": "maneuver",
                    "order": 1,
                },
            ]
        }
        path = _write(self.dir / "phrases.json", payload)
        ordered = [phrase.id for phrase in phrases.load(path).in_export_order()]
        self.assertEqual(ordered, ["man_one", "man_two", "alert_one"])

    def test_tts_text_falls_back_to_label(self) -> None:
        inventory = phrases.load()
        turn_left = inventory.require("turn_left")
        self.assertEqual(turn_left.speech_text, "Turn left")
        u_turn = inventory.require("u_turn")
        self.assertEqual(u_turn.speech_text, "Make a U turn")

    def test_set_statuses_writes_back(self) -> None:
        payload = {
            "phrases": [
                {
                    "id": "turn_left",
                    "label": "Turn left",
                    "required": True,
                    "filename": "turn_left.mp3",
                    "status": "missing",
                }
            ]
        }
        path = _write(self.dir / "phrases.json", payload)
        changed = phrases.set_statuses(path, {"turn_left": "final"})
        self.assertEqual(changed, 1)
        self.assertEqual(phrases.load(path).require("turn_left").status, "final")


class SourceCsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _csv(self, body: str) -> Path:
        path = self.dir / "sources.csv"
        path.write_text(body, encoding="utf-8")
        return path

    def test_timestamp_formats(self) -> None:
        self.assertAlmostEqual(
            sources.parse_timestamp("00:01:02.500", field="start", row_number=2), 62.5
        )
        self.assertAlmostEqual(
            sources.parse_timestamp("1:02.5", field="start", row_number=2), 62.5
        )
        self.assertAlmostEqual(sources.parse_timestamp("62.5", field="start", row_number=2), 62.5)

    def test_bad_timestamp_names_the_row(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            sources.parse_timestamp("about a minute", field="start", row_number=7)
        self.assertIn("Row 7", str(caught.exception))

    def test_duration_column_instead_of_end(self) -> None:
        path = self._csv(
            "phrase_id,source_path,start,duration\n" "turn_left,C:\\a.wav,1.0,1.5\n"
        )
        clips = sources.load(path)
        self.assertAlmostEqual(clips[0].end, 2.5)

    def test_end_before_start_rejected(self) -> None:
        path = self._csv("phrase_id,source_path,start,end\n" "turn_left,C:\\a.wav,5.0,2.0\n")
        with self.assertRaises(SystemExit):
            sources.load(path)

    def test_duplicate_take_rejected(self) -> None:
        path = self._csv(
            "phrase_id,source_path,start,end,take\n"
            "turn_left,C:\\a.wav,1.0,2.0,1\n"
            "turn_left,C:\\a.wav,3.0,4.0,1\n"
        )
        with self.assertRaises(SystemExit) as caught:
            sources.load(path)
        self.assertIn("duplicate take", str(caught.exception).lower())

    def test_two_preferred_takes_rejected(self) -> None:
        path = self._csv(
            "phrase_id,source_path,start,end,take,preferred\n"
            "turn_left,C:\\a.wav,1.0,2.0,1,1\n"
            "turn_left,C:\\a.wav,3.0,4.0,2,1\n"
        )
        with self.assertRaises(SystemExit) as caught:
            sources.load(path)
        self.assertIn("more than one preferred", str(caught.exception))

    def test_preferred_take_wins_over_lowest(self) -> None:
        path = self._csv(
            "phrase_id,source_path,start,end,take,preferred\n"
            "turn_left,C:\\a.wav,1.0,2.0,1,\n"
            "turn_left,C:\\a.wav,3.0,4.0,3,1\n"
        )
        clips = sources.load(path)
        self.assertEqual(sources.preferred_take(clips, "turn_left"), 3)

    def test_unknown_phrase_id_rejected(self) -> None:
        path = self._csv("phrase_id,source_path,start,end\n" "not_a_phrase,C:\\a.wav,1.0,2.0\n")
        with self.assertRaises(SystemExit) as caught:
            sources.load(path, known_phrase_ids={"turn_left"})
        self.assertIn("unknown phrase_id", str(caught.exception))

    def test_unknown_column_rejected(self) -> None:
        path = self._csv("phrase_id,source_path,start,end,colour\n" "turn_left,C:\\a.wav,1,2,red\n")
        with self.assertRaises(SystemExit) as caught:
            sources.load(path)
        self.assertIn("unknown column", str(caught.exception).lower())

    def test_stem_round_trip(self) -> None:
        stem = sources.clip_stem("turn_left", 3)
        self.assertEqual(stem, "turn_left__take3")
        self.assertEqual(sources.parse_stem(stem), ("turn_left", 3))
        self.assertIsNone(sources.parse_stem("turn_left"))


class TakeResolutionTests(unittest.TestCase):
    """The prefix-matching bug the scaffold shipped, pinned down."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.audio = Path(self.tmp.name)
        for name in ("processed", "synthesized", "extracted"):
            (self.audio / name).mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _touch(self, stage: str, name: str) -> Path:
        path = self.audio / stage / name
        path.write_bytes(b"RIFF")
        return path

    def test_prefix_does_not_collide(self) -> None:
        self._touch("extracted", "arrived__take1.wav")
        # `arrive` must not claim `arrived__take1.wav`.
        self.assertIsNone(takes.find("arrive", audio_root=self.audio))
        self.assertIsNotNone(takes.find("arrived", audio_root=self.audio))

    def test_takes_sort_numerically(self) -> None:
        self._touch("extracted", "turn_left__take2.wav")
        self._touch("extracted", "turn_left__take10.wav")
        found = takes.find("turn_left", audio_root=self.audio)
        assert found is not None
        self.assertEqual(found.take, 2)

    def test_preferred_take_selected(self) -> None:
        self._touch("extracted", "turn_left__take1.wav")
        self._touch("extracted", "turn_left__take3.wav")
        found = takes.find("turn_left", audio_root=self.audio, preferred_take=3)
        assert found is not None
        self.assertEqual(found.take, 3)

    def test_processed_beats_extracted(self) -> None:
        self._touch("extracted", "turn_left__take1.wav")
        self._touch("processed", "turn_left__take1.wav")
        found = takes.find("turn_left", audio_root=self.audio)
        assert found is not None
        self.assertEqual(found.origin, "processed")

    def test_synthesized_used_when_no_source_clip(self) -> None:
        self._touch("synthesized", "recalculating.wav")
        found = takes.find("recalculating", audio_root=self.audio)
        assert found is not None
        self.assertTrue(found.is_synthesized)
        self.assertIsNone(found.take)


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_shipped_routes_parse(self) -> None:
        book = routes.load()
        self.assertIn("basic_city_route", book.ids)
        route = book.get("basic_city_route")
        self.assertGreater(len(route.steps), 0)

    def test_legacy_flat_phrase_list_still_works(self) -> None:
        payload = {
            "routes": [
                {
                    "id": "legacy",
                    "label": "Legacy",
                    "pause_seconds": 1.0,
                    "phrases": ["turn_left", "turn_right"],
                }
            ]
        }
        path = _write(self.dir / "routes.json", payload)
        route = routes.load(path).get("legacy")
        self.assertEqual(len(route.steps), 2)
        self.assertEqual(route.step_gap_seconds, 1.0)
        self.assertEqual(route.phrase_ids, ["turn_left", "turn_right"])

    def test_multi_phrase_step(self) -> None:
        payload = {
            "routes": [
                {
                    "id": "chained",
                    "steps": [{"say": ["in_quarter_mile", "turn_right"], "context": "merge"}],
                }
            ]
        }
        path = _write(self.dir / "routes.json", payload)
        route = routes.load(path).get("chained")
        self.assertEqual(route.steps[0].phrase_ids, ("in_quarter_mile", "turn_right"))
        self.assertEqual(route.steps[0].context, "merge")

    def test_unknown_route_lists_alternatives(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            routes.load().get("no_such_route")
        self.assertIn("Available routes", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
