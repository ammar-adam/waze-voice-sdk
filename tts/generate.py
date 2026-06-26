"""Placeholder for optional TTS phrase generation experiments."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Placeholder for future TTS generation.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    print("TTS generation is not implemented yet. See tts/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
