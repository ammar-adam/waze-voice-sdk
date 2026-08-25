# Product Requirements Document

## Status

M0 and M1 are complete. The "Future Requirements" below are also complete: ffmpeg
extraction, optional Demucs cleanup, loudness normalization, route-like QA playback,
ordered recorder export, and optional voice synthesis with rights and consent safeguards.

The core pipeline still depends only on the Python standard library plus ffmpeg. Demucs and
the synthesis backend are isolated optional extras, and every step degrades cleanly when they are
absent.

Waze packaging claims remain deferred. No import mechanism has been verified on a real
device, and the export step is designed to work under that uncertainty rather than around
it.

## Overview

Waze Voice SDK is a Windows-first open-source toolkit for preparing custom navigation voice clips. It helps creators inventory required phrases, track source clips, validate coverage, and eventually extract, clean, normalize, QA, and export audio for a Waze custom voice workflow.

## Problem

Custom navigation voices are tedious to build by hand. Creators need a repeatable workflow for tracking required prompts, producing consistent audio clips, and preparing those clips for import into Waze's current custom voice recorder experience.

## Goals

- Maintain a configurable phrase inventory.
- Validate which required prompts have final clips.
- Keep all generated media and rights-sensitive assets out of Git.
- Support a Windows-first Python workflow.
- Provide contributor documentation for legally usable voice projects.
- Defer Waze-specific packaging claims until import mechanics are validated.

## Non-Goals

- No copyrighted audio distribution.
- No trained character or celebrity voice model distribution.
- No official Waze or Google affiliation.
- No Google Maps support in v1.
- No real-time synthesis in v1.
- No app store distribution.
- No monetization.

## MVP Requirements

### M0: Foundation

- Add repo scaffold.
- Add legal guidance.
- Add README and contributor guide.
- Add Git ignores for generated media and model artifacts.

### M1: Phrase Inventory

- Store phrase metadata in `config/phrases.json`.
- Include phrase ID, label, required flag, expected filename, status, and notes.
- Validate missing required clips in `audio/master`.
- Use only Python standard library dependencies.

## Future Requirements

- ffmpeg extraction from source media.
- Optional Demucs cleanup.
- Loudness normalization.
- Route-like QA playback.
- Ordered Waze recorder export.
- Optional TTS experiments with rights and consent safeguards.

## Success Criteria

- A fresh clone explains the project clearly.
- `python scripts/validate.py` runs on Windows.
- Required missing clips are reported clearly.
- No audio assets, model weights, or generated videos are tracked.
