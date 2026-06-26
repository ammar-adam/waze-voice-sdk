"""Placeholder for optional TTS training experiments."""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Placeholder for future TTS training.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    print("TTS training is not implemented yet. See tts/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
