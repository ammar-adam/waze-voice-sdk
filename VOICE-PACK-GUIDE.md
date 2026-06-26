# Voice Pack Guide

Use this workflow to build a legally usable custom navigation voice set.

## 1. Choose A Rights-Cleared Voice

Start with audio you can legally use and redistribute if you plan to publish it. Do not use copyrighted characters, actors, or celebrity voices without permission.

## 2. Update The Phrase Inventory

Edit `config/phrases.json`. Each phrase has:

- `id`: stable machine-readable prompt ID.
- `label`: human-readable phrase.
- `required`: whether the phrase must have a final clip.
- `filename`: expected final filename in `audio/master`.
- `status`: planning status such as `missing`, `sourced`, `synthesized`, or `final`.
- `notes`: optional production notes.

## 3. Track Source Candidates

Use `data/sources.sample.csv` as the format for your own source inventory. Keep private source files outside Git.

## 4. Produce Final Clips

Final clips should eventually be placed in `audio/master`. These files are ignored by Git.

Initial target format:

- MP3
- Mono
- 44100 Hz
- Consistent navigation-friendly loudness

## 5. Validate Coverage

Run:

```powershell
python scripts/validate.py
```

Fix missing required clips before testing in Waze.

## 6. Import Into Waze

Until a direct package import path is verified, use Waze's in-app custom voice recorder workflow and the future recorder export checklist.

Document any successful device workflow in `docs/waze-import-spike.md`.
