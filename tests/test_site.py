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

import build_site  # noqa: E402
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
            for clip in ("start", "reroute", "arrive"):
                with self.subTest(voice=voice["slug"], clip=clip):
                    path = SITE / "audio" / f"{voice['slug']}-{clip}.mp3"
                    self.assertTrue(path.is_file(), path.name)
                    self.assertGreater(path.stat().st_size, 5_000)

    def test_every_voice_has_its_words(self) -> None:
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                self.assertEqual(set(self.lines[voice["slug"]]), {"start", "reroute", "arrive"})

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


class QrTests(unittest.TestCase):
    """QR codes are committed so a static host can serve site/ untouched. A
    stale one would install the wrong pack, and nothing on screen shows it."""

    def test_each_qr_code_encodes_its_current_link(self) -> None:
        for voice in voices():
            with self.subTest(voice=voice["slug"]):
                path = SITE / "qr" / f"{voice['slug']}.svg"
                self.assertTrue(path.is_file(), f"{path.name}: run scripts/build_site.py")
                self.assertEqual(
                    path.read_bytes(),
                    build_site.qr_svg(voice["uuid"]),
                    f"{path.name} is stale: run scripts/build_site.py",
                )

    def test_no_qr_code_for_a_voice_that_is_gone(self) -> None:
        slugs = {v["slug"] for v in voices()}
        for path in (SITE / "qr").glob("*.svg"):
            with self.subTest(file=path.name):
                self.assertIn(path.stem, slugs)


class DomainTests(unittest.TestCase):
    def test_cname_is_the_launch_domain(self) -> None:
        self.assertEqual((SITE / "CNAME").read_text(encoding="utf-8").strip(), "backseatnav.com")

    def test_canonical_and_share_urls_use_the_domain(self) -> None:
        for name in (
            "index.html",
            "install.html",
            "how-it-works.html",
            "make-your-own.html",
        ):
            html = (SITE / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                for url in re.findall(
                    r'(?:canonical" href|og:url" content|og:image" content)="([^"]+)"', html
                ):
                    self.assertTrue(url.startswith("https://backseatnav.com/"), url)

    def test_every_page_carries_the_disclaimer(self) -> None:
        for name in (
            "index.html",
            "install.html",
            "how-it-works.html",
            "make-your-own.html",
        ):
            with self.subTest(page=name):
                self.assertIn(
                    "Not affiliated with Waze or Google", (SITE / name).read_text(encoding="utf-8")
                )


class AnalyticsTests(unittest.TestCase):
    """Vercel Web Analytics counts a page only if the page loads its script."""

    def pages(self) -> list[Path]:
        pages = sorted(SITE.glob("*.html"))
        self.assertTrue(pages)
        return pages

    def test_every_page_loads_vercel_web_analytics(self) -> None:
        for path in self.pages():
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=path.name):
                self.assertIn('<script defer src="/_vercel/insights/script.js"></script>', html)
                # The queue has to exist before anything calls va().
                self.assertIn("window.va = window.va || function", html)
                self.assertLess(html.index("window.va = "), html.index("</head>"))

    def test_every_page_with_a_github_link_counts_the_click(self) -> None:
        """track.js tracks github_click site-wide; a page without it goes uncounted."""
        for path in self.pages():
            html = path.read_text(encoding="utf-8")
            if 'href="https://github.com/' in html:
                with self.subTest(page=path.name):
                    self.assertIn('<script src="track.js"></script>', html)

    def test_docs_report_readership(self) -> None:
        for name in ("how-it-works.html", "make-your-own.html"):
            with self.subTest(page=name):
                self.assertIn("<body data-doc-read>", (SITE / name).read_text(encoding="utf-8"))

    def test_every_event_sends_at_most_two_properties_to_vercel(self) -> None:
        """Vercel Pro keeps 2 custom-event properties; more would be dropped."""
        js = (SITE / "track.js").read_text(encoding="utf-8")
        table = re.search(r"var VERCEL_PROPS = \{(.*?)\};", js, re.S)
        self.assertIsNotNone(table)
        entries = re.findall(r"(\w+): \[([^\]]*)\]", table.group(1))
        for name, keys in entries:
            with self.subTest(event=name):
                self.assertLessEqual(len(re.findall(r'"\w+"', keys)), 2)
        declared = {name for name, _ in entries}
        sent = re.findall(r'track\("([a-z_]+)"', (SITE / "app.js").read_text(encoding="utf-8") + js)
        for name in set(sent):
            with self.subTest(event=name):
                self.assertIn(name, declared)


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
