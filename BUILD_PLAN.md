# Waze Voice SDK Build Plan

## Project Direction

Build a Windows-first open-source toolkit for preparing custom navigation voice clips for Waze-style custom voices. The public repo must stay generic and must not include copyrighted audio, character names, extracted clips, trained voice models, or demo videos.

The private Paddington-style demo can use this toolkit locally, but it should remain outside the repository.

## Critical Validation

The current public Waze custom voice workflow appears to be the in-app custom voice recorder, not a confirmed public ZIP/manifest SDK. Before building packaging around a ZIP format, validate how Waze accepts custom voice assets today.

### Spike 0: Waze Import Mechanics

Goal: prove that a pre-rendered audio clip can become a Waze custom voice prompt and play during navigation.

Tasks:

1. Install the latest Waze app on a test device.
2. Go to `Settings > Voice and sound > Waze voice > Add a voice`.
3. Record one prompt manually.
4. Test whether an externally generated clip can be injected by one of these methods:
   - Playing the clip from PC speakers into the phone microphone.
   - Playing the clip through a virtual audio route if available.
   - On Android only, inspecting whether Waze stores custom voice recordings in app-accessible storage.
   - On Android only, testing whether a recorded prompt can be replaced without root.
5. Start a real or simulated route and confirm the custom prompt plays.
6. Document device model, OS version, Waze version, exact steps, and result in `docs/waze-import-spike.md`.

Acceptance criteria:

- At least one generated audio prompt plays inside Waze.
- The repo documents the import method clearly enough to repeat.
- If ZIP/manifest import cannot be verified, v1 uses the recorder-assisted workflow.

## MVP Scope

The MVP is not a Waze integration library. It is a voice asset production pipeline that exports ordered, normalized clips and checklists for Waze's custom voice recorder workflow.

### In Scope

- Windows setup documentation.
- Phrase inventory config.
- Source clip inventory CSV.
- ffmpeg-based extraction from local media.
- Optional Demucs cleanup hook.
- Loudness normalization.
- QA playback sequence.
- Export folder ordered by Waze prompt names.
- Validation script for missing clips and invalid audio properties.
- Contributor guide for adding legally usable voices.

### Out of Scope

- Shipping copyrighted audio.
- Shipping trained character voice model weights.
- Claiming official Waze support.
- Google Maps support.
- Real-time synthesis.
- App Store or Play Store distribution.
- Monetization.

## Repo Structure

```text
waze-voice-sdk/
  README.md
  BUILD_PLAN.md
  PRD.md
  LEGAL.md
  VOICE-PACK-GUIDE.md
  requirements.txt
  .gitignore

  config/
    phrases.json
    routes.sample.json

  data/
    sources.sample.csv

  audio/
    raw/.gitkeep
    extracted/.gitkeep
    processed/.gitkeep
    synthesized/.gitkeep
    master/.gitkeep
    export/.gitkeep

  scripts/
    extract.py
    clean.py
    normalize.py
    qa.py
    validate.py
    export_waze_recorder.py

  tts/
    README.md
    train.py
    generate.py

  docs/
    windows-setup.md
    waze-import-spike.md
    waze-import-workflow.md
    demo-video-plan.md
```

## Milestones

### M0: Repository Foundation

Tasks:

- Add repo structure.
- Add `.gitignore` that excludes audio, videos, datasets, model weights, and local media.
- Add `README.md` with project purpose, legal stance, and quick start.
- Add `LEGAL.md` explaining that users must provide rights-cleared audio.
- Add `requirements.txt`.

Acceptance criteria:

- Fresh clone has a clear README.
- No generated or copyrighted assets are tracked.
- `git status` only shows intended scaffold files.

### M1: Phrase Inventory

Tasks:

- Create `config/phrases.json`.
- Include prompt IDs, labels, required flags, expected filenames, and status fields.
- Start with a conservative sample phrase list until the current Waze app prompt list is manually confirmed.
- Add `scripts/validate.py` to report missing required clips.

Acceptance criteria:

- `python scripts/validate.py` reports phrase coverage.
- Missing required prompts are listed clearly.
- The phrase file is easy to edit without code changes.

### M2: Extraction Pipeline

Tasks:

- Create `data/sources.sample.csv`.
- Implement `scripts/extract.py`.
- Use `ffmpeg` through `subprocess`.
- Inputs: CSV rows with `phrase_id`, `source_path`, `start`, `end`, `take`, and `notes`.
- Outputs: WAV clips under `audio/extracted/`.

Acceptance criteria:

- A user can cut clips from local media with one command.
- Script fails clearly if ffmpeg is missing.
- Script validates unknown phrase IDs.

### M3: Cleanup Hook

Tasks:

- Implement `scripts/clean.py`.
- Support Demucs as an optional command.
- Copy through clips unchanged when cleanup is skipped.
- Output cleaned clips under `audio/processed/`.

Acceptance criteria:

- Cleanup can run per file or for all extracted files.
- Missing Demucs produces an actionable error.
- Processed output preserves phrase IDs.

### M4: Normalization

Tasks:

- Implement `scripts/normalize.py`.
- Target mono, 44100 Hz, MP3 output.
- Target loudness: `-16 LUFS`.
- Input priority: processed clips first, synthesized clips second, extracted clips fallback.
- Output final clips under `audio/master/`.

Acceptance criteria:

- Every exported final clip is mono MP3 at 44100 Hz.
- Loudness is consistent enough for navigation playback.
- Script reports skipped/missing clips.

### M5: QA Playback

Tasks:

- Implement `scripts/qa.py`.
- Read `config/routes.sample.json`.
- Play clips in route-like sequences.
- Add pauses between prompts.
- Print phrase IDs while playing.

Acceptance criteria:

- A user can audition a realistic route sequence.
- Missing clips are reported before playback starts.
- QA can run entirely on Windows.

### M6: Waze Recorder Export

Tasks:

- Implement `scripts/export_waze_recorder.py`.
- Copy master clips to `audio/export/` in Waze recording order.
- Generate an `IMPORT_CHECKLIST.md` with phrase labels, filenames, and recording status boxes.
- Include a short instruction block for playing each clip into the Waze recorder.

Acceptance criteria:

- Export folder is ordered and human-friendly.
- Checklist can be used during phone recording.
- No Waze ZIP/manifest claim is made unless the import spike proves it.

### M7: Optional TTS

Tasks:

- Add placeholder `tts/README.md`.
- Add `tts/train.py` and `tts/generate.py` as stubs or experimental scripts only after the base pipeline works.
- Document that generated voices must respect rights, consent, and platform rules.

Acceptance criteria:

- Base repo does not depend on TTS.
- TTS is clearly marked optional and experimental.
- No model artifacts are tracked.

### M8: Demo Launch

Tasks:

- Record real-device demo.
- Keep demo voice assets out of repo.
- Add `docs/demo-video-plan.md`.
- Update README with a link to the demo only if legally acceptable.

Acceptance criteria:

- Demo is under 60 seconds.
- Repo remains generic and rights-clean.
- README explains how others can make their own legally usable packs.

## Initial Codex Build Prompt

Use this prompt to start implementation:

```text
You are working in the waze-voice-sdk repo.

Implement milestone M0 and M1 from BUILD_PLAN.md.

Create the repo scaffold, .gitignore, README.md, LEGAL.md, PRD.md,
VOICE-PACK-GUIDE.md, requirements.txt, config/phrases.json,
config/routes.sample.json, data/sources.sample.csv, and scripts/validate.py.

Keep the project generic. Do not mention Paddington in public-facing files except
as an example of what must not be shipped. Do not include audio files, model
weights, datasets, or copyrighted assets.

Use Python 3.10+, pathlib, argparse, and JSON/CSV standard libraries only for M1.
Make validate.py check that all required phrases have corresponding files in
audio/master or are marked optional.
```

## Build Order

1. M0: Repo foundation.
2. M1: Phrase inventory and validation.
3. M2: Clip extraction.
4. M4: Normalization.
5. M6: Waze recorder export.
6. M5: QA playback.
7. M3: Cleanup hook.
8. M7: Optional TTS.
9. M8: Demo launch.

This order keeps the project useful before the harder audio and TTS pieces are complete.
