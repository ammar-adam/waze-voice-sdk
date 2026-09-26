"""The site's invariants.

The one that matters most: a UUID lives in site/voices.json and nowhere else.
Two generations of stale links shipped because UUIDs were copied into several
places and only some of them got updated. Everything else here checks that a
voice listed in voices.json has every piece the page needs to render it.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "scripts"))

import check_links  # noqa: E402

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def voices() -> list[dict]:
    return json.loads((SITE / "voices.json").read_text(encoding="utf-8"))["voices"]


class VoicesJsonTests(unittest.TestCase):
    def test_slugs_are_unique_and_url_safe(self) -> None:
        slugs = [v["slug"] for v in voices()]
        self.assertEqual(len(slugs), len(set(slugs)))
        for slug in slugs:
            self.assertRegex(slug, r"^[a-z0-9-]+$")

    def test_every_uuid_is_well_formed(self) -> None:
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                self.assertRegex(voice["uuid"], f"^{UUID.pattern}$")

    def test_every_voice_names_a_real_preset(self) -> None:
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                self.assertTrue((ROOT / "presets" / f"{voice['preset']}.json").is_file())


class SingleSourceTests(unittest.TestCase):
    def test_no_uuid_appears_outside_voices_json(self) -> None:
        """If this fails, a UUID was hardcoded somewhere it will go stale."""
        for path in list(SITE.glob("*.html")) + list(SITE.glob("*.js")) + list(SITE.glob("*.css")):
            with self.subTest(file=path.name):
                self.assertEqual(UUID.findall(path.read_text(encoding="utf-8")), [])


class CompletenessTests(unittest.TestCase):
    """A voice in voices.json with a missing piece renders as a broken card."""

    def setUp(self) -> None:
        self.lines = json.loads((SITE / "audio" / "lines.json").read_text(encoding="utf-8"))
        self.colours = (SITE / "characters.css").read_text(encoding="utf-8")

    def test_every_voice_has_three_previews(self) -> None:
        for voice in voices():
            for clip in ("turn", "reroute", "arrive"):
                with self.subTest(voice=voice["slug"], clip=clip):
                    path = SITE / "audio" / f"{voice['slug']}-{clip}.mp3"
                    self.assertTrue(path.is_file(), path.name)
                    self.assertGreater(path.stat().st_size, 5_000)

    def test_every_voice_has_its_words(self) -> None:
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                self.assertEqual(set(self.lines[voice["slug"]]), {"turn", "reroute", "arrive"})

    def test_every_voice_has_a_face(self) -> None:
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                face = SITE / "faces" / f"{voice['slug']}.svg"
                self.assertTrue(face.is_file(), face.name)
                self.assertIn("<svg", face.read_text(encoding="utf-8"))

    def test_every_voice_has_its_colours(self) -> None:
        """Without them the card falls back to the default and the Install
        button loses the character's colour."""
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                self.assertRegex(self.colours, rf"#{voice['slug']}\s*{{[^}}]*--tone:")


class DomainTests(unittest.TestCase):
    def test_cname_is_the_launch_domain(self) -> None:
        self.assertEqual((SITE / "CNAME").read_text(encoding="utf-8").strip(), "backseat.fm")

    def test_canonical_and_share_urls_use_the_domain(self) -> None:
        for name in ("index.html", "install.html"):
            html = (SITE / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                for url in re.findall(
                    r'(?:canonical" href|og:url" content|og:image" content)="([^"]+)"', html
                ):
                    self.assertTrue(url.startswith("https://backseat.fm/"), url)

    def test_every_page_carries_the_disclaimer(self) -> None:
        for name in ("index.html", "install.html"):
            with self.subTest(page=name):
                self.assertIn(
                    "Not affiliated with Waze or Google", (SITE / name).read_text(encoding="utf-8")
                )


class LinkCheckTests(unittest.TestCase):
    def _run(self, respond) -> int:
        with (
            mock.patch.object(check_links.urllib.request, "urlopen", side_effect=respond),
            mock.patch.object(check_links.time, "sleep"),
            mock.patch("builtins.print"),
        ):
            return check_links.main()

    def test_all_live_passes(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value = mock.Mock(
            status=200, headers={"Content-Length": "615000"}
        )
        self.assertEqual(self._run(lambda *a, **k: response), 0)

    def test_a_dead_pack_fails_the_run(self) -> None:
        def gone(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

        self.assertEqual(self._run(gone), 1)

    def test_an_error_page_is_not_a_pack(self) -> None:
        """A 200 with a tiny body is a CDN error page, not 600 kB of audio."""
        response = mock.MagicMock()
        response.__enter__.return_value = mock.Mock(status=200, headers={"Content-Length": "412"})
        self.assertEqual(self._run(lambda *a, **k: response), 1)


if __name__ == "__main__":
    unittest.main()
