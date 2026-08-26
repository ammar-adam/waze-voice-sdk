"""Presets: the rights rules, the navigation rules, and the size budget.

Two of these are enforcement rather than testing. A preset that clones a
performance, or that loses the number out of a distance callout, must be
impossible to ship rather than merely discouraged.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from waze_voice import budget as budget_module
from waze_voice import config as config_module
from waze_voice import phrases as phrases_module
from waze_voice import presets

SHIPPED = ("eeyore", "pooh", "tigger")


def _base_preset(**overrides) -> dict:
    """A minimal valid preset, for tests that break one thing at a time."""
    inventory = phrases_module.load()
    lines = {
        phrase.id: phrase.speech_text for phrase in inventory if phrase.in_waze_pack
    }
    data = {
        "label": "Test",
        "description": "A test preset.",
        "provider": "openai",
        "voice": "nova",
        "direction": "Speak plainly.",
        "lines": lines,
        "rights": {
            "source_work": "Some Book",
            "author": "Some Author",
            "year": 1900,
            "pd_basis": "Published 1900; US copyright expired.",
            "covered": ["The text of the book."],
            "not_covered": ["Any voice performance."],
        },
    }
    data.update(overrides)
    return data


def _validate(data: dict):
    return presets.validate_raw(
        data, name="test", inventory=phrases_module.load()
    )


class ShippedPresetTests(unittest.TestCase):
    def test_all_three_load(self) -> None:
        found = {preset.name for preset in presets.list_presets()}
        for name in SHIPPED:
            self.assertIn(name, found)

    def test_each_covers_every_waze_prompt(self) -> None:
        inventory = phrases_module.load()
        wanted = {phrase.id for phrase in inventory if phrase.in_waze_pack}
        for name in SHIPPED:
            preset = presets.load(name)
            self.assertEqual(
                set(preset.lines), wanted, f"{name} does not cover every prompt"
            )

    def test_each_passes_the_contributor_check(self) -> None:
        for name in SHIPPED:
            errors, _ = presets.check(name)
            self.assertEqual(errors, [], f"{name}: {errors}")

    def test_tigger_comes_from_the_later_book(self) -> None:
        """Tigger is not in the 1926 book, and the metadata has to say so."""
        tigger = presets.load("tigger")
        self.assertEqual(tigger.rights.year, 1928)
        self.assertIn("House at Pooh Corner", tigger.rights.source_work)

        for name in ("eeyore", "pooh"):
            preset = presets.load(name)
            self.assertEqual(preset.rights.year, 1926)
            self.assertEqual(preset.rights.source_work, "Winnie-the-Pooh")

    def test_rights_name_what_is_excluded(self) -> None:
        """The exclusions are the load-bearing half of the rights block."""
        for name in SHIPPED:
            preset = presets.load(name)
            excluded = " ".join(preset.rights.not_covered).lower()
            for expected in ("disney", "performance", "trademark"):
                self.assertIn(expected, excluded, f"{name} omits {expected}")
            # Jurisdiction is asserted separately, in JurisdictionTests, because
            # the covered and not-covered halves each carry part of it.

    def test_no_preset_names_a_reference_recording(self) -> None:
        for name in SHIPPED:
            raw = json.loads((presets.presets_dir() / f"{name}.json").read_text())
            self.assertEqual(presets.CLONING_KEYS & set(raw), set())
            self.assertEqual(
                presets.CLONING_KEYS & set(raw.get("provider_options", {})), set()
            )

    def test_presets_use_a_catalogue_voice(self) -> None:
        from waze_voice import providers

        for name in SHIPPED:
            preset = presets.load(name)
            provider = providers.get(preset.provider)
            self.assertTrue(preset.voice)
            if not provider.supports_voice_listing:
                # A fixed catalogue: the voice must actually be in it.
                catalogue = {voice.id for voice in provider("").list_voices()}
                self.assertIn(preset.voice, catalogue, f"{name} uses an unknown voice")


class CloningIsStructurallyRefusedTests(unittest.TestCase):
    """Public domain covers a work. It never covers a performance of it."""

    def test_top_level_reference_is_rejected(self) -> None:
        for key in ("reference", "speaker_wav", "audio_prompt_path", "voice_clone"):
            with self.subTest(key=key):
                preset, errors, _ = _validate(_base_preset(**{key: "sample.wav"}))
                self.assertIsNone(preset)
                self.assertTrue(any(key in error for error in errors))

    def test_reference_smuggled_through_provider_options_is_rejected(self) -> None:
        preset, errors, _ = _validate(
            _base_preset(provider_options={"speaker_wav": "actor.wav"})
        )
        self.assertIsNone(preset)
        self.assertTrue(any("clon" in error.lower() for error in errors))

    def test_a_clean_preset_still_passes(self) -> None:
        preset, errors, _ = _validate(_base_preset(provider_options={"speed": 0.9}))
        self.assertEqual(errors, [])
        self.assertIsNotNone(preset)


class RightsAreMandatoryTests(unittest.TestCase):
    def test_missing_rights_block_is_rejected(self) -> None:
        data = _base_preset()
        del data["rights"]
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("rights" in error for error in errors))

    def test_each_rights_field_is_required(self) -> None:
        for field in presets.RIGHTS_FIELDS:
            with self.subTest(field=field):
                data = _base_preset()
                data["rights"] = {k: v for k, v in data["rights"].items() if k != field}
                preset, errors, _ = _validate(data)
                self.assertIsNone(preset)
                self.assertTrue(any(field in error for error in errors))


class NavigationClarityTests(unittest.TestCase):
    """A driver who has never heard of the character still has to know what to do."""

    def test_a_distance_callout_cannot_lose_its_number(self) -> None:
        data = _base_preset()
        data["lines"]["in_quarter_mile"] = "In a little while, I should think."
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("in_quarter_mile" in error for error in errors))

    def test_a_turn_cannot_lose_its_direction(self) -> None:
        data = _base_preset()
        data["lines"]["turn_left"] = "Go the way you were going before, but not."
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("turn_left" in error for error in errors))

    def test_an_ordinal_cannot_lose_its_number(self) -> None:
        data = _base_preset()
        data["lines"]["exit_third"] = "take one of the exits."
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)

    def test_shipped_presets_keep_every_required_token(self) -> None:
        for name in SHIPPED:
            preset = presets.load(name)
            for phrase_id, alternatives in presets.REQUIRED_TOKENS.items():
                line = preset.lines.get(phrase_id, "").lower()
                for options in alternatives:
                    self.assertTrue(
                        any(token in line for token in options),
                        f"{name}/{phrase_id}: {line!r} lost {options}",
                    )

    def test_missing_lines_are_rejected(self) -> None:
        data = _base_preset()
        del data["lines"]["turn_left"]
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("turn_left" in error for error in errors))


class LineLengthTests(unittest.TestCase):
    """Flavour goes where it is cheap. Frequently-heard prompts stay short."""

    def test_a_long_high_frequency_line_is_rejected(self) -> None:
        data = _base_preset()
        data["lines"]["turn_left"] = (
            "Turn left, and I do mean left, the other left, the one on the side "
            "where your heart is, more or less, roughly speaking."
        )
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("turn_left" in error for error in errors))

    def test_low_frequency_lines_may_be_longer(self) -> None:
        data = _base_preset()
        data["lines"]["exit_seventh"] = (
            "take the seventh exit, which is a great many exits, and I am not "
            "entirely sure why this roundabout needed so many of them."
        )
        preset, errors, _ = _validate(data)
        self.assertEqual(errors, [])
        self.assertIsNotNone(preset)

    def test_shipped_presets_respect_the_limits(self) -> None:
        inventory = phrases_module.load()
        weights = {phrase.id: phrase.weight for phrase in inventory}
        for name in SHIPPED:
            preset = presets.load(name)
            for phrase_id, line in preset.lines.items():
                limit = (
                    presets.MAX_CHARS_HIGH_FREQUENCY
                    if weights.get(phrase_id, 1.0) >= presets.HIGH_FREQUENCY_WEIGHT
                    else presets.MAX_CHARS_OTHER
                )
                self.assertLessEqual(len(line), limit, f"{name}/{phrase_id}")


class PresetBudgetTests(unittest.TestCase):
    """Every preset against the cap, not just the one that was built first.

    Clip length varies per preset two ways: the lines differ, and the delivery
    speed differs. Eeyore is slower than the default voice, which is exactly the
    case that a pack sitting at 98.6% of the cap would have failed on.
    """

    def _estimate(self, preset: presets.Preset, cfg) -> budget_module.AllocationPlan:
        inventory = phrases_module.load()
        padding = (cfg.trim.lead_in_ms + cfg.trim.lead_out_ms) / 1000.0

        durations = presets.estimate_durations(preset, inventory, padding=padding)
        weights = {
            phrase.waze_filename: phrase.weight
            for phrase in inventory
            if phrase.in_waze_pack
        }
        specs = [
            budget_module.ClipSpec(
                filename=filename,
                source=Path(filename),
                duration=seconds,
                weight=weights.get(filename, 1.0),
            )
            for filename, seconds in durations.items()
        ]

        plan = budget_module.allocate(
            specs,
            budget_bytes=int(cfg.export.budget_bytes * cfg.export.target_utilisation)
            - cfg.export.overhead_reserve_bytes,
            strategy=cfg.export.strategy,
            min_kbps=cfg.export.min_kbps,
            max_kbps=cfg.export.max_kbps,
            sample_rate_policy=cfg.export.sample_rate_policy,
        )
        plan.budget_bytes = cfg.export.budget_bytes
        plan.target_utilisation = cfg.export.target_utilisation
        plan.fail_above_utilisation = cfg.export.fail_above_utilisation
        return plan

    def test_every_preset_fits_with_headroom(self) -> None:
        cfg = config_module.load()
        for name in SHIPPED:
            with self.subTest(preset=name):
                plan = self._estimate(presets.load(name), cfg)
                self.assertLessEqual(
                    plan.utilisation,
                    cfg.export.fail_above_utilisation,
                    f"{name} at {plan.utilisation:.1%}",
                )
                self.assertEqual(plan.notes, [], f"{name}: {plan.notes}")

    def test_no_preset_is_squeezed_to_the_bitrate_floor(self) -> None:
        """Fitting by pinning everything to the floor is fitting badly.

        Utilisation alone hides this: the allocator always spends up to the
        target, so a preset in trouble looks identical until you check what
        bitrate its clips actually got.
        """
        cfg = config_module.load()
        for name in SHIPPED:
            with self.subTest(preset=name):
                plan = self._estimate(presets.load(name), cfg)
                floored = [
                    item
                    for item in plan.allocations
                    if item.bitrate_kbps <= cfg.export.min_kbps
                ]
                self.assertLess(
                    len(floored),
                    len(plan.allocations) // 2,
                    f"{name}: {len(floored)}/{len(plan.allocations)} clips at the floor",
                )

    def test_high_weight_prompts_get_real_bitrate(self) -> None:
        cfg = config_module.load()
        for name in SHIPPED:
            plan = self._estimate(presets.load(name), cfg)
            turn_left = plan.get("TurnLeft.mp3")
            self.assertIsNotNone(turn_left)
            assert turn_left is not None
            self.assertGreaterEqual(
                turn_left.bitrate_kbps, 64, f"{name}: turn_left starved"
            )


class PresetLoadingTests(unittest.TestCase):
    def test_unknown_preset_lists_the_real_ones(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            presets.load("nonesuch")
        self.assertIn("eeyore", str(caught.exception))

    def test_traversal_in_a_preset_name_is_rejected(self) -> None:
        for name in ("../secrets", "..", "a/b"):
            with self.subTest(name=name), self.assertRaises(SystemExit):
                presets.load(name)

    def test_list_skips_a_broken_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "broken.json").write_text("{not json", encoding="utf-8")
            good = _base_preset()
            (directory / "good.json").write_text(json.dumps(good), encoding="utf-8")
            with mock.patch.object(presets, "presets_dir", return_value=directory):
                names = {preset.name for preset in presets.list_presets()}
        self.assertEqual(names, {"good"})

    def test_text_for_falls_back(self) -> None:
        preset = presets.load("eeyore")
        self.assertEqual(preset.text_for("not_a_phrase", "fallback"), "fallback")
        self.assertEqual(preset.text_for("turn_left", "fallback"), "Turn left.")


class WordBoundaryTests(unittest.TestCase):
    """Substring matching let "leftover" satisfy a left turn."""

    def test_normalise_flattens_punctuation_and_case(self) -> None:
        self.assertEqual(presets.normalise("Make a U-turn!"), "make a u turn")
        self.assertEqual(presets.normalise("In 1.5 kilometers."), "in 1 5 kilometers")

    def test_contains_word_is_whole_word(self) -> None:
        self.assertTrue(presets.contains_word("Turn left.", "left"))
        self.assertFalse(presets.contains_word("Take the leftover lane.", "left"))
        self.assertFalse(presets.contains_word("Cleft the rock.", "left"))

    def test_contains_word_handles_phrases_and_hyphens(self) -> None:
        self.assertTrue(presets.contains_word("Make a U-turn.", "u turn"))
        self.assertTrue(presets.contains_word("In half a mile.", "half a mile"))
        self.assertFalse(presets.contains_word("In half a minute.", "half a mile"))

    def test_a_substring_match_no_longer_passes_validation(self) -> None:
        data = _base_preset()
        data["lines"]["turn_left"] = "Take the leftover lane."
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("turn_left" in error for error in errors))


class AmbiguityTests(unittest.TestCase):
    """Containing the right word is not the same as being unambiguous."""

    def test_naming_both_directions_is_rejected(self) -> None:
        for phrase_id, line in (
            ("turn_left", "Turn left, not right."),
            ("turn_right", "Go right, definitely not left."),
            ("keep_left", "Keep left, the right lane is closed."),
        ):
            with self.subTest(phrase_id=phrase_id):
                data = _base_preset()
                data["lines"][phrase_id] = line
                preset, errors, _ = _validate(data)
                self.assertIsNone(preset)
                self.assertTrue(any("landed last" in error for error in errors))

    def test_naming_two_exits_is_rejected(self) -> None:
        data = _base_preset()
        data["lines"]["exit_third"] = "Not the second, take the third exit."
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("more than one exit" in error for error in errors))

    def test_naming_two_distances_is_rejected(self) -> None:
        data = _base_preset()
        data["lines"]["in_half_mile"] = "In half a mile, or a quarter of a mile."
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("more than one distance" in error for error in errors))

    def test_shipped_presets_are_unambiguous(self) -> None:
        for name in SHIPPED:
            preset = presets.load(name)
            for phrase_id, line in preset.lines.items():
                self.assertEqual(
                    presets._ambiguity_errors(phrase_id, line), [], f"{name}/{phrase_id}"
                )


class SplitSpeechRateTests(unittest.TestCase):
    """A character can be fast where nothing is at stake and sober where it is."""

    def test_navigation_critical_classification(self) -> None:
        self.assertTrue(presets.is_navigation_critical("turn_left", 3.0))
        self.assertTrue(presets.is_navigation_critical("exit_third", 0.7))
        self.assertTrue(presets.is_navigation_critical("and_then", 2.5))
        self.assertFalse(presets.is_navigation_critical("start_drive_1", 1.0))
        self.assertFalse(presets.is_navigation_critical("reroute_chime", 0.3))

    def test_tigger_slows_down_for_instructions(self) -> None:
        tigger = presets.load("tigger")
        self.assertTrue(tigger.critical_provider_options)
        fast = tigger.options_for("start_drive_1", 1.0)["speed"]
        careful = tigger.options_for("turn_left", 3.0)["speed"]
        self.assertGreater(fast, careful)
        self.assertLessEqual(careful, 1.0, "instructions must not be sped up")

    def test_presets_without_a_split_are_uniform(self) -> None:
        eeyore = presets.load("eeyore")
        self.assertEqual(
            eeyore.options_for("start_drive_1", 1.0),
            eeyore.options_for("turn_left", 3.0),
        )

    def test_critical_options_cannot_smuggle_cloning(self) -> None:
        data = _base_preset(critical_provider_options={"speaker_wav": "actor.wav"})
        preset, errors, _ = _validate(data)
        self.assertIsNone(preset)
        self.assertTrue(any("clon" in error.lower() for error in errors))


class JurisdictionTests(unittest.TestCase):
    """Public domain is per country, and the docs have to say which."""

    def test_canada_and_uk_are_both_stated(self) -> None:
        for name in SHIPPED:
            rights = presets.load(name).rights
            covered = " ".join(rights.covered).lower()
            not_covered = " ".join(rights.not_covered).lower()
            self.assertIn("canada", covered, f"{name} does not state Canada")
            self.assertIn("united states", covered, f"{name} does not state the US")
            self.assertIn("2027", not_covered, f"{name} does not state the UK/EU date")


class EstimatorTests(unittest.TestCase):
    def test_estimate_scales_with_length_and_speed(self) -> None:
        slow = presets.estimate_seconds("a" * 140, speed=0.5)
        fast = presets.estimate_seconds("a" * 140, speed=2.0)
        self.assertGreater(slow, fast)

    def test_short_lines_hit_a_floor(self) -> None:
        self.assertGreaterEqual(
            presets.estimate_seconds("Go."), presets.MIN_CLIP_SECONDS
        )

    def test_padding_is_added(self) -> None:
        bare = presets.estimate_seconds("Turn left.")
        padded = presets.estimate_seconds("Turn left.", padding=0.5)
        self.assertAlmostEqual(padded - bare, 0.5, places=3)

    def test_estimate_durations_uses_the_split_rate(self) -> None:
        inventory = phrases_module.load()
        durations = presets.estimate_durations(presets.load("tigger"), inventory)
        self.assertIn("TurnLeft.mp3", durations)
        self.assertEqual(len(durations), 43)


if __name__ == "__main__":
    unittest.main()
