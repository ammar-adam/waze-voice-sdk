"""The site's security headers, and the page code they have to agree with.

vercel.json sends a Content-Security-Policy with every response. A CSP that
drifts out of step with the pages fails quietly: a blocked script or font is
a console message nobody reads. So every inline script must be hashed in the
policy, every third-party script or stylesheet must be allowed by it, and no
page may rely on something the policy forbids (inline handlers, javascript:
links). The page scripts must never turn visitor-supplied text into HTML.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)
EXTERNAL_SCRIPT = re.compile(r'<script[^>]*\bsrc="(https?:)?//([^/"]+)')
EXTERNAL_STYLE = re.compile(r'<link[^>]*rel="stylesheet"[^>]*href="(https?:)?//([^/"]+)')


def headers() -> dict[str, str]:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    for rule in config.get("headers", []):
        if rule["source"] == "/(.*)":
            return {h["key"].lower(): h["value"] for h in rule["headers"]}
    return {}


def csp() -> dict[str, list[str]]:
    policy = headers().get("content-security-policy", "")
    out: dict[str, list[str]] = {}
    for part in policy.split(";"):
        words = part.split()
        if words:
            out[words[0]] = words[1:]
    return out


def pages() -> list[Path]:
    return sorted(SITE.rglob("*.html"))


class HeaderTests(unittest.TestCase):
    def test_every_response_carries_the_security_headers(self) -> None:
        sent = headers()
        self.assertEqual(sent.get("x-content-type-options"), "nosniff")
        self.assertEqual(sent.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertEqual(sent.get("x-frame-options"), "DENY")
        self.assertIn("max-age=", sent.get("strict-transport-security", ""))
        self.assertIn("camera=()", sent.get("permissions-policy", ""))

    def test_the_policy_is_strict_where_it_matters(self) -> None:
        policy = csp()
        self.assertEqual(policy.get("default-src"), ["'self'"])
        self.assertEqual(policy.get("object-src"), ["'none'"])
        self.assertEqual(policy.get("frame-ancestors"), ["'none'"])
        self.assertEqual(policy.get("base-uri"), ["'self'"])
        self.assertIn("'self'", policy.get("media-src", []), "the film and the previews")
        scripts = policy.get("script-src", [])
        self.assertNotIn("'unsafe-inline'", scripts)
        self.assertNotIn("'unsafe-eval'", scripts)
        self.assertNotIn("*", scripts)


class PagesFitThePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = csp()
        self.assertTrue(pages())

    def test_every_inline_script_is_hashed_in_the_policy(self) -> None:
        """Change an inline script and its hash changes: update vercel.json."""
        allowed = set(self.policy.get("script-src", []))
        for path in pages():
            html = path.read_text(encoding="utf-8")
            for body in INLINE_SCRIPT.findall(html):
                digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
                with self.subTest(page=str(path.relative_to(SITE)), script=body[:40]):
                    self.assertIn(f"'sha256-{digest}'", allowed)

    def test_every_third_party_script_and_stylesheet_is_allowed(self) -> None:
        scripts = self.policy.get("script-src", [])
        styles = self.policy.get("style-src", [])
        for path in pages():
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=str(path.relative_to(SITE))):
                for _, host in EXTERNAL_SCRIPT.findall(html):
                    self.assertIn(f"https://{host}", scripts)
                for _, host in EXTERNAL_STYLE.findall(html):
                    self.assertIn(f"https://{host}", styles)

    def test_fonts_come_from_where_the_policy_allows(self) -> None:
        fonts = self.policy.get("font-src", [])
        for path in pages():
            if "fonts.googleapis.com" in path.read_text(encoding="utf-8"):
                self.assertIn("https://fonts.gstatic.com", fonts)
                break

    def test_no_page_relies_on_inline_handlers_or_javascript_links(self) -> None:
        for path in pages():
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=str(path.relative_to(SITE))):
                self.assertNotRegex(html, r"<[^>]+\son[a-z]+\s*=")
                self.assertNotRegex(html.lower(), r"href=\"\s*javascript:")

    def test_no_media_or_frames_from_elsewhere(self) -> None:
        for path in pages():
            html = path.read_text(encoding="utf-8")
            with self.subTest(page=str(path.relative_to(SITE))):
                self.assertNotRegex(html, r"<(iframe|object|embed)\b")
                for tag in re.findall(r"<(?:video|audio|source|img)\b[^>]*>", html):
                    for url in re.findall(r'(?:src|poster)="([^"]+)"', tag):
                        self.assertFalse(urlsplit(url).netloc, f"{url}: media-src is 'self'")


class NoHtmlFromVisitorsTests(unittest.TestCase):
    """Suggestion names are typed by strangers and shown to everyone."""

    SAFE_RHS = re.compile(r"""^(\s|\+|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|ARROW)+$""")

    def test_html_is_only_ever_built_from_literals_or_escaped_text(self) -> None:
        for path in sorted(SITE.glob("*.js")):
            js = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotRegex(
                    js, r"insertAdjacentHTML|document\.write|outerHTML\s*=|\beval\("
                )
                for rhs in re.findall(r"\.innerHTML\s*=\s*([^;]*);", js):
                    if rhs.strip() == "html.trim()":  # app.js el(): its callers escape
                        continue
                    self.assertRegex(rhs, self.SAFE_RHS, rhs[:80])

    def test_suggestion_names_are_escaped_or_set_as_text(self) -> None:
        app = (SITE / "app.js").read_text(encoding="utf-8")
        for match in re.finditer(r"item\.name", app):
            before = app[max(0, match.start() - 60) : match.start()]
            with self.subTest(at=match.start()):
                self.assertRegex(before, r"(escapeHtml\(|toast\(|send\()[^;]*$")
        stats = (SITE / "stats.js").read_text(encoding="utf-8")
        self.assertIn('node("span", "name", item.name)', stats)  # textContent


if __name__ == "__main__":
    unittest.main()
