"""Publish the repository's documentation as static pages under site/docs/.

    python scripts/build_docs.py          # write site/docs/*.html
    python scripts/build_docs.py --check  # fail if the committed pages are stale

Vercel serves site/ untouched with no build step, so the generated HTML is
committed. Run this after editing README.md, CHANGELOG.md, the root guides or
anything in docs/, and commit the result.

Sources: README.md becomes site/docs/index.html (the docs home, with a list of
every page), each docs/<name>.md becomes site/docs/<name>.html, and the root
guides (CHANGELOG, VOICE-PACK-GUIDE, CONTRIBUTING, SECURITY, LEGAL,
CODE_OF_CONDUCT) are published alongside. Links between published docs are
rewritten to the generated pages; links to anything else in the repository go
to GitHub.

Before anything is written, every source is scanned for things that must not
be public (API keys, tokens, email addresses, local user paths). Local paths
are redacted; anything that looks like a credential stops the build, and the
report names the file and line but never prints the value.

Needs the `markdown` package (requirements-dev.txt): pip install markdown
"""

from __future__ import annotations

import argparse
import html
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

try:
    import markdown
    from markdown.extensions import Extension
    from markdown.treeprocessors import Treeprocessor
except ModuleNotFoundError:  # pragma: no cover - reported, not raised
    sys.exit("build_docs.py needs the markdown package: python -m pip install markdown")

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUT = SITE / "docs"
GITHUB = "https://github.com/ammar-adam/waze-voice-sdk"
BLOB = f"{GITHUB}/blob/main/"
EDIT = f"{GITHUB}/edit/main/"
DOMAIN = "https://backseatnav.com"

# ---------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Doc:
    source: str  # repo-relative, forward slashes
    slug: str  # output file stem
    label: str  # short name for the sidebar
    blurb: str  # one line for the docs home


# Order within a group is the reading order. Every docs/*.md must appear here;
# the build fails on one that does not, so a new doc cannot go missing quietly.
GROUPS: list[tuple[str, str, list[Doc]]] = [
    (
        "Start here",
        "What the toolkit is, and one voice from start to finish.",
        [
            Doc(
                "README.md",
                "index",
                "Overview",
                "What this repository is, and the fastest route to a pack",
            ),
            Doc(
                "VOICE-PACK-GUIDE.md",
                "voice-pack-guide",
                "Voice pack guide",
                "Building a pack from your own recordings, step by step",
            ),
            Doc(
                "docs/windows-setup.md",
                "windows-setup",
                "Windows setup",
                "ffmpeg, Python, and the Windows-specific traps",
            ),
        ],
    ),
    (
        "Guides",
        "Doing a specific job.",
        [
            Doc(
                "docs/tts.md",
                "tts",
                "Synthesis and TTS",
                "The four providers, what each is good at, and the rights each raises",
            ),
            Doc(
                "docs/presets.md",
                "presets",
                "Presets",
                "How a character is defined, and how to add one",
            ),
            Doc(
                "docs/upload-runbook.md",
                "upload-runbook",
                "Upload runbook",
                "Getting a finished pack onto Waze, start to finish",
            ),
            Doc(
                "docs/waze-import-workflow.md",
                "waze-import-workflow",
                "Getting a pack into Waze",
                "How Waze packs actually work, and what fails silently",
            ),
        ],
    ),
    (
        "Reference",
        "How it works, and what was measured.",
        [
            Doc(
                "docs/pipeline.md",
                "pipeline",
                "Pipeline design",
                "What each step does to the audio, and why",
            ),
            Doc(
                "docs/audio-targets.md",
                "audio-targets",
                "Audio targets",
                "Loudness and size targets, and where the numbers came from",
            ),
            Doc(
                "docs/waze-import-spike.md",
                "waze-import-spike",
                "Real-pack findings",
                "What was measured from eleven real packs, and what is still open",
            ),
            Doc("CHANGELOG.md", "changelog", "Changelog", "What changed, and when"),
        ],
    ),
    (
        "Project",
        "Working on the toolkit itself.",
        [
            Doc(
                "CONTRIBUTING.md",
                "contributing",
                "Contributing",
                "Setup, house style, and what CI checks",
            ),
            Doc(
                "SECURITY.md",
                "security",
                "Security",
                "How to report a vulnerability, and what is in scope",
            ),
            Doc(
                "LEGAL.md",
                "legal",
                "Legal notes",
                "What belongs in the repository, and what never does",
            ),
            Doc("CODE_OF_CONDUCT.md", "code-of-conduct", "Code of conduct", "Be decent"),
        ],
    ),
    (
        "Behind the scenes",
        "Planning notes from making the launch films. Kept for the record; the film "
        "that shipped may differ.",
        [
            Doc(
                "docs/launch-film.md",
                "launch-film",
                "Launch film plan",
                "The first cut, built around the missed turn",
            ),
            Doc(
                "docs/film-line-sheet.md",
                "film-line-sheet",
                "Film line sheet",
                "Every line the films may use, cut from the live packs",
            ),
            Doc(
                "docs/demo-video-plan.md",
                "demo-video-plan",
                "Filming a demo",
                "Showing a pack on a real device without leaking it",
            ),
        ],
    ),
]

DOCS: list[Doc] = [d for _, _, docs in GROUPS for d in docs]
BY_SOURCE = {d.source: d for d in DOCS}

# ---------------------------------------------------------------- what must not be public

# Rewritten in the published copy, never in the source. (pattern, replacement, why)
REDACT: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+\\waze-voice-sdk"),
        r"C:\\path\\to\\waze-voice-sdk",
        "a local Windows user path",
    ),
    (
        re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"'<]+"),
        r"C:\\Users\\you",
        "a local Windows user path",
    ),
    (
        re.compile(
            r"^I'll quote the credit cost from the Runway API before generating anything\.\n", re.M
        ),
        "",
        "a working note to the film's author, not documentation",
    ),
]

# Anything matching these stops the build. Values are never printed.
SECRETS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI-style key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{20,}")),
    (
        "key assigned a value",
        re.compile(
            r"(?i)\b[A-Z_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\b\s*[=:]\s*[\"']?(?!<|sk-\.\.\.|\$)[A-Za-z0-9_\-]{16,}"
        ),
    ),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("pack UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")),
]


def mask(value: str) -> str:
    return value[:3] + "*" * max(len(value) - 3, 3)


def scan(source: str, text: str) -> list[str]:
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in SECRETS:
            for m in pattern.finditer(line):
                problems.append(f"{source}:{lineno}: {name} ({mask(m.group(0))})")
    return problems


def redact(text: str) -> tuple[str, list[str]]:
    notes = []
    for pattern, replacement, why in REDACT:
        text, n = pattern.subn(replacement, text)
        if n:
            notes.append(f"{n} x {why}")
    return text, notes


def prepare(doc: Doc, text: str) -> str:
    """Source-level trims that make a GitHub page read as a web page."""
    if doc.source == "README.md":
        # CI and licence badges: GitHub furniture, and third-party images.
        text = "\n".join(line for line in text.splitlines() if not line.startswith("[!["))
    # The page supplies its own <h1>; drop the document's.
    text = re.sub(r"\A\s*# .+\n", "", text, count=1)
    return text


def title_of(text: str) -> str:
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------- link rewriting


def resolve(doc: Doc, href: str) -> str:
    """Where a link in `doc` should point from site/docs/<slug>.html."""
    if not href or href.startswith(("#", "mailto:")):
        return href
    parts = urlsplit(href)
    if parts.scheme or href.startswith("//"):
        return href
    # Resolve exactly as GitHub does: relative to the file's blob URL.
    absolute = urljoin(BLOB + doc.source, href)
    parts = urlsplit(absolute)
    if absolute.startswith(BLOB):
        path = posixpath.normpath(parts.path[len(urlsplit(BLOB).path) :])
        target = BY_SOURCE.get(path)
        if target is not None:
            page = f"{target.slug}.html" if target.slug != "index" else "./"
            if parts.fragment:
                return f"{page}#{parts.fragment}" if target is not doc else f"#{parts.fragment}"
            return page
        tree = "tree" if (REPO / path).is_dir() else "blob"
        url = f"{GITHUB}/{tree}/main/{path}"
        return url + (f"#{parts.fragment}" if parts.fragment else "")
    return absolute  # ../../issues and the like: the repository on GitHub


class LinkRewriter(Treeprocessor):
    def __init__(self, md: markdown.Markdown, doc: Doc) -> None:
        super().__init__(md)
        self.doc = doc

    def run(self, root: ET.Element) -> None:
        for el in root.iter():
            if el.tag == "a" and el.get("href") is not None:
                el.set("href", resolve(self.doc, el.get("href", "")))
            elif el.tag == "img" and el.get("src"):
                src = el.get("src", "")
                if not urlsplit(src).scheme:
                    # Docs images are served from GitHub rather than copied.
                    path = posixpath.normpath(
                        posixpath.join(posixpath.dirname(self.doc.source), src)
                    )
                    el.set(
                        "src",
                        f"https://raw.githubusercontent.com/ammar-adam/waze-voice-sdk/main/{path}",
                    )
                el.set("loading", "lazy")


class DocsExtension(Extension):
    def __init__(self, doc: Doc) -> None:
        super().__init__()
        self.doc = doc

    def extendMarkdown(self, md: markdown.Markdown) -> None:  # noqa: N802 (markdown's API)
        md.treeprocessors.register(LinkRewriter(md, self.doc), "docs_links", 5)


def render(doc: Doc, text: str) -> tuple[str, list[dict]]:
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "sane_lists", "toc", DocsExtension(doc)],
        extension_configs={"toc": {"toc_depth": "2-3"}},
        output_format="html",
    )
    body = md.convert(text)
    # Tables scroll on their own on a phone rather than widening the page.
    body = re.sub(r"<table>", '<div class="table-scroll"><table>', body)
    body = body.replace("</table>", "</table></div>")

    # GitHub task lists.
    def task(m: re.Match[str]) -> str:
        para = (m.group(1) or "").strip()
        done = " done" if m.group(2) == "x" else ""
        return f'<li class="task">{para}<span class="box{done}" aria-hidden="true"></span>'

    body = re.sub(r"<li>(\s*<p>)?\[( |x)\]\s*", task, body)
    body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', body)
    return body, md.toc_tokens


# ---------------------------------------------------------------- page template

FONTS = (
    "https://fonts.googleapis.com/css2?family=Bagel+Fat+One&family=Bricolage+Grotesque:"
    "opsz,wght@12..96,400;12..96,600;12..96,700&family=JetBrains+Mono:wght@500&display=swap"
)
GITHUB_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/>'
    '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>'
)


def head_scripts() -> str:
    """The analytics block, copied from a hand-written page so the docs never
    drift from whatever the rest of the site loads (and however it loads it)."""
    page = (SITE / "how-it-works.html").read_text(encoding="utf-8")
    head = page[: page.index("</head>")]
    tags = re.findall(r"<script\b[^>]*>.*?</script>", head, re.S)
    out = []
    for tag in tags:
        tag = re.sub(r'src="(?!/|https?:)([^"]+)"', lambda m: f'src="../{m.group(1)}"', tag)
        out.append("  " + tag)
    return "\n".join(out)


def nav(current: str | None = None) -> str:
    items = [
        ("nav-voices", "../#voices", "Voices"),
        ("nav-film", "../film.html", "Film"),
        ("", "../how-it-works.html", "How it works"),
        ("", "../make-your-own.html", "Make your own"),
        ("nav-docs", "./", "Docs"),
        ("nav-stats", "../stats.html", "Stats"),
        ("nav-gh", GITHUB, "GitHub"),
    ]
    links = []
    for cls, href, label in items:
        attrs = f' class="{cls}"' if cls else ""
        if label == "Docs":
            attrs += ' aria-current="page"' if current == "index" else ' aria-current="true"'
        links.append(f'        <a{attrs} href="{href}">{label}</a>')
    return "\n".join(links)


def doc_list(current: Doc) -> str:
    groups = []
    for name, _, docs in GROUPS:
        items = []
        for d in docs:
            href = "./" if d.slug == "index" else f"{d.slug}.html"
            cur = ' aria-current="page"' if d is current else ""
            items.append(f'<li><a href="{href}"{cur}>{html.escape(d.label)}</a></li>')
        groups.append(f'<p class="group">{html.escape(name)}</p>\n<ul>{"".join(items)}</ul>')
    return "\n".join(groups)


def on_this_page(tokens: list[dict]) -> str:
    h2s = [t for t in tokens if t["level"] == 2] or [
        c for t in tokens for c in t.get("children", []) if c["level"] == 2
    ]
    if len(h2s) < 3:
        return ""
    items = "".join(
        f'<li><a href="#{t["id"]}">{html.escape(html.unescape(t["name"]))}</a></li>' for t in h2s
    )
    return (
        '<nav class="toc sticker" aria-label="On this page">'
        f"<b>On this page</b><ol>{items}</ol></nav>"
    )


def home_catalogue() -> str:
    cards = []
    for name, blurb, docs in GROUPS:
        items = []
        for d in docs:
            if d.slug == "index":
                continue
            items.append(
                f'<li><a href="{d.slug}.html">{html.escape(d.label)}</a>'
                f"<span>{html.escape(d.blurb)}</span></li>"
            )
        cards.append(
            f'<section class="docs-group sticker"><h2>{html.escape(name)}</h2>'
            f"<p>{html.escape(blurb)}</p><ul>{''.join(items)}</ul></section>"
        )
    return f'<div class="docs-groups">{"".join(cards)}</div>'


def page(doc: Doc, title: str, body: str, tokens: list[dict]) -> str:
    is_home = doc.slug == "index"
    url = f"{DOMAIN}/docs/" + ("" if is_home else f"{doc.slug}.html")
    page_title = "Backseat docs" if is_home else f"{title} | Backseat docs"
    h1 = "Docs" if is_home else html.escape(title)
    description = (
        "The Backseat toolkit's documentation: build a custom Waze voice pack, "
        "from presets and synthesis to upload."
        if is_home
        else doc.blurb + "."
    )
    kicker = "Documentation" if is_home else next(g for g, _, ds in GROUPS if doc in ds)
    if is_home:
        intro = (
            '<p class="standfirst">Everything in the repository\'s documentation, '
            "as web pages. Start with the overview below, or jump to a guide.</p>\n"
            f"{home_catalogue()}\n"
            '<h2 id="overview" class="docs-overview">Overview</h2>'
        )
    else:
        # No standfirst: every doc opens with its own first line.
        intro = on_this_page(tokens)
    menu = doc_list(doc)
    # On a phone the doc list folds into a menu above the page. The docs home
    # lists everything in its body already, so it goes without.
    phone_menu = (
        ""
        if is_home
        else (
            '      <details class="docs-menu sticker">\n'
            "        <summary>All docs</summary>\n"
            '        <nav class="docs-list" aria-label="Documentation">\n'
            f"{menu}\n"
            "        </nav>\n"
            "      </details>\n"
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="canonical" href="{url}">
  <meta name="theme-color" content="#ffd23f">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{url}">
  <meta property="og:title" content="{html.escape(page_title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:image" content="{DOMAIN}/og.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{FONTS}">
  <link rel="stylesheet" href="../style.css">
  <link rel="stylesheet" href="../docs.css">
{head_scripts()}
</head>
<body data-doc-read>
  <!-- Generated by scripts/build_docs.py from {doc.source}. Edit that, not this. -->
  <header class="bar">
    <div class="wrap">
      <a class="logo sticker" href="../"><span class="lamp" aria-hidden="true"></span>Backseat</a>
      <nav aria-label="Site">
{nav(doc.slug)}
      </nav>
    </div>
  </header>

  <div class="wrap docs-layout">
    <aside class="docs-side" aria-label="Documentation">
      <nav class="docs-list">
{menu}
      </nav>
    </aside>

    <main class="doc docs-main">
{phone_menu}      <p class="kicker">{html.escape(kicker)}</p>
      <h1>{h1}</h1>
      {intro}
      <article class="prose">
{body}
      </article>
      <p class="docs-edit">
        <a class="btn plain" href="{EDIT}{doc.source}">{GITHUB_ICON}Edit on GitHub</a>
        <span>Source: <a href="{BLOB}{doc.source}"><code>{html.escape(doc.source)}</code></a></span>
      </p>
    </main>
  </div>

  <footer>
    <div class="wrap">
      <span>Independent fan project. Not affiliated with Waze, Google, or the owners of any
      character or person featured.</span>
      <nav class="foot-links">
        <a href="../">Voices</a>
        <a href="../film.html">Film</a>
        <a href="./">Docs</a>
        <a href="../stats.html">Live stats</a>
        <a href="{GITHUB}">GitHub</a>
      </nav>
    </div>
  </footer>
</body>
</html>
"""


# ---------------------------------------------------------------- checks


def check_links(pages: dict[str, str]) -> list[str]:
    """Every local href and #anchor in the generated pages must resolve."""
    problems = []
    ids = {name: set(re.findall(r'\bid="([^"]+)"', text)) for name, text in pages.items()}
    for name, text in pages.items():
        for href in re.findall(r'\bhref="([^"]+)"', text):
            if urlsplit(href).scheme or href.startswith("//"):
                continue
            path, _, frag = href.partition("#")
            if not path:
                target = name
            elif path == "./":
                target = "index.html"
            elif path.startswith("../"):
                rel = path[3:] or "index.html"
                if not (SITE / rel).is_file():
                    problems.append(f"docs/{name}: {href} -> site/{rel} is missing")
                continue
            else:
                target = path
            if target not in pages:
                problems.append(f"docs/{name}: {href} -> docs/{target} is not generated")
            elif frag and frag not in ids[target]:
                problems.append(f"docs/{name}: {href} -> no #{frag} in docs/{target}")
    return problems


def build() -> tuple[dict[str, str], list[str], list[str]]:
    listed = {d.source for d in DOCS}
    unlisted = sorted(
        p.relative_to(REPO).as_posix()
        for p in (REPO / "docs").glob("*.md")
        if p.relative_to(REPO).as_posix() not in listed
    )
    if unlisted:
        sys.exit("Not in GROUPS in scripts/build_docs.py, so not published: " + ", ".join(unlisted))

    pages: dict[str, str] = {}
    problems: list[str] = []
    notes: list[str] = []
    for doc in DOCS:
        path = REPO / doc.source
        if not path.is_file():
            if doc.source == "CHANGELOG.md":
                continue
            sys.exit(f"missing source: {doc.source}")
        raw = path.read_text(encoding="utf-8")
        text, redactions = redact(raw)
        notes += [f"{doc.source}: redacted {r}" for r in redactions]
        problems += scan(doc.source, text)
        title = title_of(text) or doc.label
        body, tokens = render(doc, prepare(doc, text))
        pages[f"{doc.slug}.html"] = page(doc, title, body, tokens)
    problems += check_links(pages)
    return pages, problems, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if site/docs/ is stale")
    args = parser.parse_args()

    pages, problems, notes = build()
    for note in notes:
        print(f"  {note}")
    if problems:
        print("Refusing to publish:")
        for p in problems:
            print(f"  {p}")
        return 1

    if args.check:
        stale = [
            n
            for n, text in pages.items()
            if not (OUT / n).is_file() or (OUT / n).read_text(encoding="utf-8") != text
        ]
        extra = sorted(p.name for p in OUT.glob("*.html") if p.name not in pages)
        if stale or extra:
            print("site/docs/ is stale; run scripts/build_docs.py:", ", ".join(stale + extra))
            return 1
        print(f"site/docs/ is current ({len(pages)} pages)")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.html"):
        if old.name not in pages:
            old.unlink()
    for name, text in pages.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(pages)} pages to site/docs/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
