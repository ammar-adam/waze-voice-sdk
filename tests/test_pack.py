"""Waze pack rules and the size-budget allocator.

Pure logic, no ffmpeg. These cover the two things that fail silently on a real
device: a filename Waze does not recognise, and a pack that is one byte over the
aggregate limit.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from waze_voice import budget, phrases, wazepack


class WazeSlotTests(unittest.TestCase):
    def test_filename_list_is_complete_and_consistent(self) -> None:
        self.assertEqual(len(wazepack.SLOTS), len(wazepack.VALID_FILENAMES))
        self.assertEqual(len(wazepack.SLOTS), 43)
        self.assertEqual(set(wazepack.BY_FILENAME), wazepack.VALID_FILENAMES)

    def test_distance_callouts_are_split_by_unit_system(self) -> None:
        metric = {s.filename for s in wazepack.SLOTS if s.units == wazepack.UNITS_METRIC}
        imperial = {s.filename for s in wazepack.SLOTS if s.units == wazepack.UNITS_IMPERIAL}

        self.assertEqual(
            metric,
            {"200meters.mp3", "400meters.mp3", "800meters.mp3", "1000meters.mp3", "1500meters.mp3"},
        )
        self.assertEqual(imperial, {"200.mp3", "400.mp3", "800.mp3", "1500.mp3"})
        self.assertFalse(metric & imperial)

    def test_bare_numbers_are_imperial_not_metric(self) -> None:
        """200.mp3 is the 0.1 mile callout. The name is misleading on purpose."""
        self.assertEqual(wazepack.BY_FILENAME["200.mp3"].units, wazepack.UNITS_IMPERIAL)
        self.assertIn("mile", wazepack.BY_FILENAME["200.mp3"].meaning)
        self.assertEqual(wazepack.BY_FILENAME["1500.mp3"].meaning, "In one mile")

    def test_slots_for_units_excludes_the_other_set(self) -> None:
        metric = {slot.filename for slot in wazepack.slots_for_units(wazepack.UNITS_METRIC)}
        self.assertIn("200meters.mp3", metric)
        self.assertNotIn("200.mp3", metric)
        self.assertIn("TurnLeft.mp3", metric, "unit-agnostic slots belong to both")

    def test_core_filenames_narrow_by_unit_system(self) -> None:
        both = wazepack.core_filenames()
        metric_only = wazepack.core_filenames(wazepack.UNITS_METRIC)
        self.assertLess(len(metric_only), len(both))
        self.assertNotIn("200.mp3", metric_only)

    def test_unknown_filenames_are_flagged(self) -> None:
        unknown = wazepack.unknown_filenames({"TurnLeft.mp3", "TurnLeftt.mp3", "500.mp3"})
        self.assertEqual(unknown, {"TurnLeftt.mp3", "500.mp3"})

    def test_slots_for_units_rejects_nonsense(self) -> None:
        with self.assertRaises(ValueError):
            wazepack.slots_for_units("furlongs")


def _clips(shape: list[tuple[str, float, float]]) -> list[budget.ClipSpec]:
    return [
        budget.ClipSpec(filename=name, source=Path(name), duration=duration, weight=weight)
        for name, duration, weight in shape
    ]


class LadderTests(unittest.TestCase):
    def test_snap_down_never_rounds_up(self) -> None:
        self.assertEqual(budget.snap_down(47.9, budget.MPEG1_BITRATES), 40)
        self.assertEqual(budget.snap_down(48.0, budget.MPEG1_BITRATES), 48)
        self.assertEqual(budget.snap_down(1.0, budget.MPEG1_BITRATES), 32)

    def test_next_lower_walks_the_ladder(self) -> None:
        self.assertEqual(budget.next_lower(48, budget.MPEG1_BITRATES), 40)
        self.assertIsNone(budget.next_lower(32, budget.MPEG1_BITRATES))

    def test_sub_32_requires_the_lower_sample_rate(self) -> None:
        """MPEG-1 has no rung below 32 kbps; 22.05 kHz is the only way down."""
        rate, ladder = budget._resolve_sample_rate(24.0, budget.POLICY_AUTO)
        self.assertEqual(rate, budget.SAMPLE_RATE_LOW)
        self.assertIn(24, ladder)

        rate, ladder = budget._resolve_sample_rate(24.0, budget.POLICY_FIXED)
        self.assertEqual(rate, budget.SAMPLE_RATE_FULL)
        self.assertEqual(ladder, budget.MPEG1_BITRATES)


class AllocationTests(unittest.TestCase):
    SHAPE = [
        ("TurnLeft.mp3", 0.9, 3.0),
        ("TurnRight.mp3", 0.9, 3.0),
        ("AndThen.mp3", 0.6, 2.5),
        ("Arrive.mp3", 1.4, 2.0),
        ("Seventh.mp3", 1.0, 0.3),
        ("StartDrive1.mp3", 9.0, 0.3),
    ]

    def test_fits_the_budget_or_says_why_not(self) -> None:
        """The contract, precisely.

        Below the quality floor there is nothing left to give: a pack long
        enough that even ``min_kbps`` overshoots cannot be made to fit by
        allocating differently. Silently dropping under the floor would trade a
        rejected upload for an unusable one, so the plan overshoots and says so,
        and the export step turns that into a failed run.
        """
        for scale in (1, 3, 10, 30):
            clips = _clips([(n, d * scale, w) for n, d, w in self.SHAPE])
            plan = budget.allocate(clips, budget_bytes=400_000, min_kbps=24)

            if plan.total_predicted_bytes > 400_000:
                self.assertTrue(
                    plan.notes,
                    f"scale {scale} overshot the budget without explaining why",
                )
                self.assertTrue(
                    all(item.bitrate_kbps <= 24 for item in plan.allocations),
                    f"scale {scale} overshot while clips were still above the floor",
                )
            else:
                self.assertFalse(plan.notes, f"scale {scale} fits but reported a problem")

    def test_a_feasible_budget_is_always_respected(self) -> None:
        for scale in (1, 2, 4, 6):
            clips = _clips([(n, d * scale, w) for n, d, w in self.SHAPE])
            plan = budget.allocate(clips, budget_bytes=400_000, min_kbps=24)
            if not plan.notes:
                self.assertLessEqual(
                    plan.total_predicted_bytes, 400_000, f"overshot at scale {scale}"
                )

    def test_weighted_favours_short_important_clips(self) -> None:
        # Scaled up so the budget actually binds.
        clips = _clips([(n, d * 4, w) for n, d, w in self.SHAPE])
        plan = budget.allocate(clips, budget_bytes=400_000, strategy="weighted")

        turn = plan.get("TurnLeft.mp3")
        greeting = plan.get("StartDrive1.mp3")
        assert turn is not None and greeting is not None
        self.assertGreater(turn.bitrate_kbps, greeting.bitrate_kbps)

    def test_uniform_gives_everything_the_same_rate(self) -> None:
        clips = _clips([(n, d * 4, w) for n, d, w in self.SHAPE])
        plan = budget.allocate(clips, budget_bytes=400_000, strategy="uniform")
        self.assertEqual(len({item.bitrate_kbps for item in plan.allocations}), 1)

    def test_weighted_uses_at_least_as_much_of_the_budget_as_uniform(self) -> None:
        """Otherwise the extra machinery is not earning its place."""
        clips = _clips([(n, d * 4, w) for n, d, w in self.SHAPE])
        weighted = budget.allocate(clips, budget_bytes=400_000, strategy="weighted")
        uniform = budget.allocate(clips, budget_bytes=400_000, strategy="uniform")
        self.assertGreaterEqual(weighted.total_predicted_bytes, uniform.total_predicted_bytes)

    def test_roomy_budget_puts_everything_at_the_ceiling(self) -> None:
        clips = _clips(self.SHAPE)
        plan = budget.allocate(clips, budget_bytes=5_000_000, max_kbps=96)
        self.assertEqual({item.bitrate_kbps for item in plan.allocations}, {96})

    def test_floor_is_respected_and_reported(self) -> None:
        clips = _clips([(n, d * 50, w) for n, d, w in self.SHAPE])
        plan = budget.allocate(clips, budget_bytes=50_000, min_kbps=24)
        self.assertTrue(all(item.bitrate_kbps >= 24 for item in plan.allocations))
        self.assertTrue(plan.notes, "an impossible budget should say so")

    def test_zero_budget_does_not_crash(self) -> None:
        plan = budget.allocate(_clips(self.SHAPE), budget_bytes=0)
        self.assertEqual(len(plan.allocations), len(self.SHAPE))

    def test_zero_duration_clips_are_dropped(self) -> None:
        clips = _clips([("TurnLeft.mp3", 0.0, 1.0), ("Arrive.mp3", 1.0, 1.0)])
        plan = budget.allocate(clips, budget_bytes=100_000)
        self.assertEqual([item.filename for item in plan.allocations], ["Arrive.mp3"])

    def test_unknown_strategy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            budget.allocate(_clips(self.SHAPE), budget_bytes=1000, strategy="vibes")

    def test_reduce_to_fit_targets_the_worst_value_clip(self) -> None:
        clips = _clips(self.SHAPE)
        plan = budget.allocate(clips, budget_bytes=5_000_000, max_kbps=128)
        for item in plan.allocations:
            item.actual_bytes = item.predicted_bytes

        reduced = budget.reduce_to_fit(plan)
        assert reduced is not None
        # Biggest file, lowest weight: the greeting, not a turn instruction.
        self.assertEqual(reduced.filename, "StartDrive1.mp3")
        self.assertLess(reduced.bitrate_kbps, 128)

    def test_reduce_to_fit_gives_up_at_the_floor(self) -> None:
        clips = _clips([("TurnLeft.mp3", 1.0, 1.0)])
        plan = budget.allocate(clips, budget_bytes=1_000, min_kbps=24)
        for _ in range(20):
            if budget.reduce_to_fit(plan, min_kbps=24) is None:
                break
        else:
            self.fail("reduce_to_fit never reported exhaustion")


class PhraseWazeFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _entry(self, **overrides) -> dict:
        entry = {
            "id": "turn_left",
            "label": "Turn left",
            "required": True,
            "filename": "turn_left.mp3",
            "status": "missing",
            "waze_filename": "TurnLeft.mp3",
            "units": "any",
            "weight": 2.0,
        }
        entry.update(overrides)
        return entry

    def test_valid_entry_parses(self) -> None:
        parsed, errors = phrases.validate_raw({"phrases": [self._entry()]})
        self.assertEqual(errors, [])
        self.assertTrue(parsed[0].in_waze_pack)
        self.assertEqual(parsed[0].weight, 2.0)

    def test_typo_in_waze_filename_is_caught(self) -> None:
        """Waze ignores unknown names silently, so this has to fail here instead."""
        _, errors = phrases.validate_raw({"phrases": [self._entry(waze_filename="TurnLef.mp3")]})
        self.assertTrue(any("TurnLef.mp3" in error for error in errors))

    def test_units_must_match_the_slot(self) -> None:
        _, errors = phrases.validate_raw(
            {"phrases": [self._entry(waze_filename="200meters.mp3", units="imperial")]}
        )
        self.assertTrue(any("metric" in error for error in errors))

    def test_two_phrases_cannot_claim_one_slot(self) -> None:
        first = self._entry()
        second = self._entry(id="turn_left_alt", filename="turn_left_alt.mp3")
        _, errors = phrases.validate_raw({"phrases": [first, second]})
        self.assertTrue(any("both claim" in error for error in errors))

    def test_negative_weight_rejected(self) -> None:
        _, errors = phrases.validate_raw({"phrases": [self._entry(weight=-1)]})
        self.assertTrue(any("weight" in error for error in errors))

    def test_shipped_inventory_covers_every_waze_slot(self) -> None:
        inventory = phrases.load()
        claimed = {phrase.waze_filename for phrase in inventory if phrase.in_waze_pack}
        self.assertEqual(claimed, wazepack.VALID_FILENAMES)

    def test_shipped_inventory_units_agree_with_the_slots(self) -> None:
        for phrase in phrases.load():
            if not phrase.in_waze_pack:
                continue
            self.assertEqual(
                phrase.units,
                wazepack.BY_FILENAME[phrase.waze_filename].units,
                phrase.id,
            )


if __name__ == "__main__":
    unittest.main()
