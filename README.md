# Waze Voice SDK

Windows-first tooling for preparing custom navigation voice clips for Waze-style custom voices.

This repo is a generic audio production pipeline. It does not include copyrighted audio, character voices, trained model weights, extracted clips, or finished voice packs. Users are responsible for providing audio they have the right to use.

## Status

Early build. Current scope covers repository foundation, phrase inventory, and validation.

The current public Waze custom voice workflow appears to be the in-app custom voice recorder. A ZIP or manifest-based import path is not assumed until it is verified on a real device.

## Quick Start

Requirements:

- Windows
- Python 3.10+

Validate the sample phrase inventory:

```powershell
python scripts/validate.py
```

The validator checks `config/phrases.json` and reports which required prompts are missing from `audio/master`.

## Project Shape

- `config/phrases.json`: navigation phrase inventory.
- `data/sources.sample.csv`: sample source clip inventory.
- `audio/master`: final normalized clips, excluded from Git.
- `scripts/validate.py`: phrase and audio coverage validation.
- `VOICE-PACK-GUIDE.md`: contributor workflow.
- `LEGAL.md`: rights and usage constraints.

## Legal Boundary

Do not commit copyrighted media, extracted clips, synthesized celebrity or character voices, trained model weights, demo videos, or assets you do not have rights to distribute.

This project is not affiliated with Waze, Google, or any rights holder.
