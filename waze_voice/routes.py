"""QA route definitions.

A real navigation prompt is usually two clips spoken as one breath ("In 500
meters" + "turn right"), then a longer gap before the next instruction. Routes
model that as *steps* containing one or more phrases, which is what makes the QA
playback sound like driving rather than like a word list.

The older flat ``{"phrases": [...]}`` shape is still accepted and is expanded to
one phrase per step.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import paths


@dataclass(frozen=True)
class RouteStep:
    phrase_ids: tuple[str, ...]
    context: str = ""

    @property
    def label(self) -> str:
        return " + ".join(self.phrase_ids)


@dataclass(frozen=True)
class Route:
    id: str
    label: str
    steps: tuple[RouteStep, ...]
    step_gap_seconds: float | None = None
    phrase_gap_seconds: float | None = None
    notes: str = ""

    @property
    def phrase_ids(self) -> list[str]:
        return [phrase_id for step in self.steps for phrase_id in step.phrase_ids]


@dataclass
class RouteBook:
    routes: list[Route] = field(default_factory=list)

    def get(self, route_id: str | None) -> Route:
        if not self.routes:
            raise SystemExit("The routes file must contain at least one route.")
        if route_id is None:
            return self.routes[0]
        for route in self.routes:
            if route.id == route_id:
                return route
        available = ", ".join(route.id for route in self.routes)
        raise SystemExit(f"Route not found: {route_id}. Available routes: {available}")

    @property
    def ids(self) -> list[str]:
        return [route.id for route in self.routes]


def _parse_step(raw: Any, route_id: str, index: int) -> RouteStep:
    location = f"route '{route_id}' step {index}"

    if isinstance(raw, str):
        return RouteStep(phrase_ids=(raw,))

    if isinstance(raw, list):
        if not all(isinstance(item, str) for item in raw):
            raise SystemExit(f"{location}: every phrase id must be a string.")
        if not raw:
            raise SystemExit(f"{location}: step must name at least one phrase.")
        return RouteStep(phrase_ids=tuple(raw))

    if isinstance(raw, dict):
        say = raw.get("say", raw.get("phrases"))
        if isinstance(say, str):
            say = [say]
        if not isinstance(say, list) or not say:
            raise SystemExit(f"{location}: 'say' must be a non-empty list of phrase ids.")
        if not all(isinstance(item, str) for item in say):
            raise SystemExit(f"{location}: every phrase id in 'say' must be a string.")
        return RouteStep(phrase_ids=tuple(say), context=str(raw.get("context", "")))

    raise SystemExit(f"{location}: expected a phrase id, a list, or an object.")


def _parse_route(raw: Any, index: int) -> Route:
    if not isinstance(raw, dict):
        raise SystemExit(f"routes[{index}] must be an object.")

    route_id = str(raw.get("id") or f"route_{index}")
    label = str(raw.get("label") or route_id)

    raw_steps = raw.get("steps")
    if raw_steps is None:
        # Legacy schema: a flat list of phrase ids, one instruction each.
        legacy = raw.get("phrases")
        if not isinstance(legacy, list) or not legacy:
            raise SystemExit(f"route '{route_id}' must define 'steps' or 'phrases'.")
        raw_steps = [[phrase_id] for phrase_id in legacy]

    if not isinstance(raw_steps, list) or not raw_steps:
        raise SystemExit(f"route '{route_id}': 'steps' must be a non-empty list.")

    steps = tuple(
        _parse_step(raw_step, route_id, position)
        for position, raw_step in enumerate(raw_steps, start=1)
    )

    step_gap = raw.get("step_gap_seconds", raw.get("pause_seconds"))
    phrase_gap = raw.get("phrase_gap_seconds")

    return Route(
        id=route_id,
        label=label,
        steps=steps,
        step_gap_seconds=float(step_gap) if step_gap is not None else None,
        phrase_gap_seconds=float(phrase_gap) if phrase_gap is not None else None,
        notes=str(raw.get("notes", "")),
    )


def load(path: Path | None = None) -> RouteBook:
    path = path or paths.routes_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing routes file: {path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON in {path}: {error}") from None

    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object in {path}")

    raw_routes = data.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise SystemExit(f"{path} must contain a non-empty 'routes' list.")

    routes = [_parse_route(raw, index) for index, raw in enumerate(raw_routes, start=1)]

    seen: set[str] = set()
    for route in routes:
        if route.id in seen:
            raise SystemExit(f"Duplicate route id in {path}: {route.id}")
        seen.add(route.id)

    return RouteBook(routes=routes)
