"""The environment check.

Doctor's whole value is being right about what is wrong. A check that reports
"ok" for something broken is worse than no check, because it sends people
looking somewhere else.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from waze_voice import doctor, providers


def _named(checks: list[doctor.Check], fragment: str) -> doctor.Check:
    for check in checks:
        if fragment in check.name:
            return check
    raise AssertionError(f"no check named like {fragment!r} in {[c.name for c in checks]}")


class ProviderKeyTests(unittest.TestCase):
    """Three states, not two. A placeholder is its own case."""

    def _check(self, env: dict[str, str]) -> doctor.Check:
        with mock.patch.dict(os.environ, env, clear=True):
            return _named(doctor._provider_checks(), "openai")

    def test_a_real_key_is_ok(self) -> None:
        check = self._check({"OPENAI_API_KEY": "sk-proj-" + "a" * 40})
        self.assertEqual(check.status, "ok")

    def test_an_unset_key_is_a_warning_with_a_signup_link(self) -> None:
        check = self._check({})
        self.assertEqual(check.status, "warn")
        self.assertIn("not set", check.detail)
        self.assertIn("http", check.blocks)

    def test_a_placeholder_is_called_a_placeholder(self) -> None:
        """It satisfies every emptiness check and then fails as a 401 partway
        through a build, so it cannot be reported as present."""
        check = self._check({"OPENAI_API_KEY": "sk-..."})
        self.assertEqual(check.status, "warn")
        self.assertIn("placeholder", check.detail)

    def test_a_short_key_is_not_mistaken_for_real(self) -> None:
        check = self._check({"OPENAI_API_KEY": "abc123"})
        self.assertEqual(check.status, "warn")

    def test_every_registered_provider_is_reported(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            checks = doctor._provider_checks()
        reported = " ".join(check.name for check in checks)
        for name in providers.NAMES:
            self.assertIn(name, reported)


class CollectTests(unittest.TestCase):
    def test_collect_returns_checks_with_valid_statuses(self) -> None:
        checks = doctor.collect()
        self.assertTrue(checks)
        for check in checks:
            with self.subTest(check=check.name):
                self.assertIn(check.status, {"ok", "warn", "missing"})
                self.assertTrue(check.detail, f"{check.name} has no detail")

    def test_every_status_has_a_symbol(self) -> None:
        """An unrecognised status renders as [??], which would be a silent
        display bug rather than a loud one."""
        for status in ("ok", "warn", "missing"):
            with self.subTest(status=status):
                check = doctor.Check(name="x", status=status, detail="d")
                self.assertNotEqual(check.symbol, "[??]")

    def test_ffmpeg_is_reported_as_required(self) -> None:
        checks = doctor.collect()
        ffmpeg = _named(checks, "ffmpeg")
        self.assertIn(ffmpeg.status, {"ok", "missing"}, "ffmpeg is not optional")


if __name__ == "__main__":
    unittest.main()
