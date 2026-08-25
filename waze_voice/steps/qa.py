"""Step 5: audition the pack as a navigation sequence before committing to it.

Playing eighteen clips alphabetically tells you almost nothing. What catches
problems is hearing "In 500 meters ... turn right" the way Waze actually chains
them, at driving volume, with the gaps a real route has. This step renders each
route step as one continuous piece of audio, optionally over a road-noise bed,
and records a pass/fail verdict per step.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import console, media, paths, phrases as phrases_module, routes as routes_module
from ..config import PipelineConfig

PASS = "pass"
FAIL = "fail"
SKIPPED = "skipped"

_HELP = (
    "  [Enter] pass    r replay    f fail    s skip    b back    q quit and save"
)


@dataclass
class StepVerdict:
    index: int
    phrase_ids: list[str]
    verdict: str
    note: str = ""


@dataclass
class QAResult:
    route_id: str = ""
    verdicts: list[StepVerdict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    rendered: Path | None = None
    report_path: Path | None = None

    @property
    def failed_phrase_ids(self) -> list[str]:
        failed: list[str] = []
        for verdict in self.verdicts:
            if verdict.verdict == FAIL:
                failed.extend(verdict.phrase_ids)
        return sorted(set(failed))

    @property
    def ok(self) -> bool:
        return not self.missing and not self.failed_phrase_ids


def _resolve_sequence(
    route: routes_module.Route,
    inventory: phrases_module.PhraseInventory,
    master_dir: Path,
) -> tuple[list[tuple[routes_module.RouteStep, list[Path]]], list[str]]:
    """Map every route step to real files, collecting anything missing."""
    resolved: list[tuple[routes_module.RouteStep, list[Path]]] = []
    missing: list[str] = []

    for step in route.steps:
        step_paths: list[Path] = []
        for phrase_id in step.phrase_ids:
            phrase = inventory.get(phrase_id)
            if phrase is None:
                missing.append(f"{phrase_id} (not in phrases.json)")
                continue
            path = master_dir / phrase.filename
            if not path.is_file():
                missing.append(f"{phrase_id} ({phrase.filename})")
                continue
            step_paths.append(path)
        if step_paths:
            resolved.append((step, step_paths))

    return resolved, missing


def _render_step(
    step_paths: list[Path],
    destination: Path,
    *,
    config: PipelineConfig,
    phrase_gap: float,
) -> Path:
    """Render one instruction, chaining its phrases with a short breath gap."""
    if len(step_paths) == 1:
        return step_paths[0]

    clips = [(path, phrase_gap) for path in step_paths[:-1]]
    clips.append((step_paths[-1], 0.0))
    return media.concat_with_gaps(
        clips,
        destination,
        sample_rate=config.audio.sample_rate,
        channels=config.audio.channels,
    )


def _prompt(index: int, total: int, label: str, context: str) -> str:
    suffix = f"  [{context}]" if context else ""
    print(f"\n({index}/{total}) {label}{suffix}")
    print(_HELP)
    try:
        return input("  > ").strip().lower()
    except EOFError:
        return "q"


def run(
    *,
    config: PipelineConfig,
    phrases_path: Path | None = None,
    routes_path: Path | None = None,
    route_id: str | None = None,
    master_dir: Path | None = None,
    render_to: Path | None = None,
    bed: Path | None = None,
    bed_gain_db: float = -20.0,
    interactive: bool = True,
    dry_run: bool = False,
    report_path: Path | None = None,
) -> QAResult:
    console.step("QA")

    inventory = phrases_module.load(phrases_path)
    book = routes_module.load(routes_path)
    route = book.get(route_id)
    master_dir = master_dir or paths.master_dir()

    step_gap = route.step_gap_seconds if route.step_gap_seconds is not None else config.qa.step_gap_seconds
    phrase_gap = (
        route.phrase_gap_seconds if route.phrase_gap_seconds is not None else config.qa.phrase_gap_seconds
    )

    result = QAResult(route_id=route.id)
    resolved, missing = _resolve_sequence(route, inventory, master_dir)
    result.missing = missing

    console.info(f"Route: {route.label} ({len(route.steps)} instruction(s))")
    if route.notes:
        console.detail(route.notes)

    if missing:
        console.bullets("Missing clips; QA cannot run until these exist:", missing)
        return result

    if dry_run:
        for index, (step, step_paths) in enumerate(resolved, start=1):
            names = ", ".join(path.name for path in step_paths)
            context = f"  [{step.context}]" if step.context else ""
            console.detail(f"{index:>2}. {step.label}{context}  ->  {names}")
        return result

    work_dir = paths.work_dir() / "qa"
    work_dir.mkdir(parents=True, exist_ok=True)

    # -- whole-route render -------------------------------------------------
    if render_to is not None:
        clips: list[tuple[Path, float]] = []
        for position, (_, step_paths) in enumerate(resolved):
            last_step = position == len(resolved) - 1
            for offset, path in enumerate(step_paths):
                last_phrase = offset == len(step_paths) - 1
                if not last_phrase:
                    gap = phrase_gap
                elif last_step:
                    gap = 0.0
                else:
                    gap = step_gap
                clips.append((path, gap))

        media.concat_with_gaps(
            clips,
            render_to,
            lead_silence=config.qa.lead_silence_seconds,
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            bed=bed,
            bed_gain_db=bed_gain_db,
        )
        result.rendered = render_to
        console.ok(f"Rendered route to {render_to}")
        console.detail(
            "Copy this onto your phone and play it through the car audio you will "
            "actually navigate with. Problems that vanish on desktop speakers show "
            "up there."
        )
        return result

    # -- step-by-step playback ---------------------------------------------
    if interactive and not sys.stdin.isatty():
        console.warn("stdin is not interactive; playing straight through without prompts.")
        interactive = False

    total = len(resolved)
    index = 0
    while index < total:
        step, step_paths = resolved[index]
        playable = _render_step(
            step_paths,
            work_dir / f"step_{index + 1:02d}.wav",
            config=config,
            phrase_gap=phrase_gap,
        )

        if not interactive:
            console.detail(f"({index + 1}/{total}) {step.label}")
            media.play(playable)
            result.verdicts.append(
                StepVerdict(index=index + 1, phrase_ids=list(step.phrase_ids), verdict=SKIPPED)
            )
            time.sleep(step_gap)
            index += 1
            continue

        media.play(playable)
        answer = _prompt(index + 1, total, step.label, step.context)

        if answer in ("", "p", "pass"):
            result.verdicts.append(
                StepVerdict(index=index + 1, phrase_ids=list(step.phrase_ids), verdict=PASS)
            )
            index += 1
        elif answer in ("r", "replay"):
            continue
        elif answer in ("f", "fail"):
            try:
                note = input("  note (optional): ").strip()
            except EOFError:
                note = ""
            result.verdicts.append(
                StepVerdict(
                    index=index + 1,
                    phrase_ids=list(step.phrase_ids),
                    verdict=FAIL,
                    note=note,
                )
            )
            index += 1
        elif answer in ("s", "skip"):
            result.verdicts.append(
                StepVerdict(index=index + 1, phrase_ids=list(step.phrase_ids), verdict=SKIPPED)
            )
            index += 1
        elif answer in ("b", "back"):
            index = max(0, index - 1)
            # Drop the verdict being revisited so it can be re-recorded.
            result.verdicts = [v for v in result.verdicts if v.index != index + 1]
        elif answer in ("q", "quit"):
            console.info("Stopping early; saving the verdicts recorded so far.")
            break
        else:
            console.warn(f"Unrecognized input {answer!r}.")

    result.report_path = _write_report(result, route, report_path)

    passed = sum(1 for verdict in result.verdicts if verdict.verdict == PASS)
    failed = sum(1 for verdict in result.verdicts if verdict.verdict == FAIL)
    console.info(f"QA complete: {passed} passed, {failed} failed, {total} step(s) in route.")

    if result.failed_phrase_ids:
        console.bullets("Phrases marked fail (re-cut, re-clean, or re-synthesize):", result.failed_phrase_ids)

    return result


def _write_report(result: QAResult, route: routes_module.Route, path: Path | None) -> Path:
    path = path or paths.qa_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    runs = existing.get("routes", {}) if isinstance(existing, dict) else {}
    runs[route.id] = {
        "label": route.label,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "steps": [asdict(verdict) for verdict in result.verdicts],
        "failed_phrase_ids": result.failed_phrase_ids,
    }

    payload = {"schema_version": 1, "routes": runs}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    console.detail(f"Wrote QA report to {path}")
    return path
