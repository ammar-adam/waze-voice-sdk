"""Audition the pack as a navigation route. Equivalent to: wvs.py qa"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from waze_voice import config as config_module
from waze_voice import console, paths
from waze_voice import routes as routes_module
from waze_voice.steps import qa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play final clips in a route-like QA sequence.")
    parser.add_argument("--phrases", type=Path, help="Phrase inventory JSON.")
    parser.add_argument("--routes", type=Path, help="Route sequence JSON.")
    parser.add_argument("--route-id", help="Route ID to play. Defaults to the first route.")
    parser.add_argument("--master-dir", type=Path, help="Directory containing final clips.")
    parser.add_argument("--config", type=Path, help="Path to pipeline.json.")
    parser.add_argument("--render", type=Path, metavar="OUT", help="Render the route to a file.")
    parser.add_argument("--bed", type=Path, help="Background bed mixed under a render.")
    parser.add_argument("--bed-db", type=float, default=-20.0, help="Bed level in dB.")
    parser.add_argument("--auto", action="store_true", help="Play through without prompting.")
    parser.add_argument("--dry-run", action="store_true", help="Print the sequence only.")
    parser.add_argument("--list-routes", action="store_true")
    parser.add_argument(
        "--pack",
        help="Voice pack to work on. See: python scripts/wvs.py pack list",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    console.set_quiet(args.quiet)
    if args.pack:
        paths.set_active_pack(args.pack)
        console.detail(f"Pack: {args.pack}")

    if args.list_routes:
        book = routes_module.load(args.routes)
        console.bullets(
            "Available routes:",
            [f"{route.id}: {route.label} ({len(route.steps)} steps)" for route in book.routes],
        )
        return 0

    result = qa.run(
        config=config_module.load(args.config),
        phrases_path=args.phrases,
        routes_path=args.routes,
        route_id=args.route_id,
        master_dir=args.master_dir,
        render_to=args.render,
        bed=args.bed,
        bed_gain_db=args.bed_db,
        interactive=not args.auto,
        dry_run=args.dry_run,
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
