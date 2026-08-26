# Changelog

Notable changes. Dates are when the work landed on `main`.

## Unreleased

### Added

- **Multiple voice packs from one clone.** `packs/<name>/` holds a voice's own
  source list, audio tree, and optional config overrides. Every command takes
  `--pack`, or set `WVS_PACK` once. `wvs pack new|list|show` manages them.
  Packs share the Waze slot list and fall back to `config/` per file, so a pack
  usually needs only its own `sources.csv`.

- CI on GitHub Actions: ruff and mypy, the test suite on Windows and Linux
  across Python 3.10 to 3.13, and an end-to-end pack build that uploads the
  resulting pack as an artifact.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates
  (including one for real-device reports), and a pull request template.

### Fixed

- **Data loss.** `export --export-dir` cleared its target recursively, so
  pointing it at a directory with anything else in it deleted that too. It now
  refuses to remove files it did not create; `--force` is the explicit opt-out.
- `max_kbps` below 32 with `sample_rate_policy: fixed` returned 32 kbps anyway,
  quietly exceeding the ceiling that protects the size budget. The contradiction
  is now rejected when the allocation starts.
- mypy is clean. Fixing it turned up `cmd_run` reusing one variable for six
  different result types.

## 0.2.0

### Added

- **The full pipeline**: extract, clean, synth, normalize, qa, export, plus a
  `wvs` command that runs them end to end and a `doctor` that reports what is
  missing and which step it blocks.
- **Waze pack building.** All 43 filenames Waze recognises, both metric and
  imperial distance sets, and per-clip bitrate allocation to fit Waze's
  undocumented ~0.8 MB aggregate limit. Around 99.8% budget utilisation against
  a flat bitrate's 88.9%.
- **Voice synthesis** via Chatterbox, chosen over XTTS-v2 and F5-TTS because its
  weights are MIT rather than non-commercial. Optional throughout: the pipeline
  skips it cleanly and routes unfilled prompts to the checklist.
- Route-based QA that chains prompts the way Waze speaks them, with pass/fail
  verdicts and optional road-noise bed rendering.
- A test suite that generates its own audio, so a fresh clone can verify itself
  without any media.

### Fixed

- Clip matching used a prefix glob, so `arrive` claimed `arrived__take1.wav` and
  `take10` sorted before `take2`.
- Demucs mode lost every phrase ID, because Demucs writes
  `<out>/<model>/<track>/vocals.wav` rather than flat files.
- Normalization used single-pass `loudnorm`, which runs in dynamic mode and
  pumps on short material.
- EBU R128 cannot measure a sub-two-second prompt. Clips are padded with silence
  before measurement; gating discards the padding.
- Extraction paired an input-side `-ss` with an output-side one, which is applied
  after the filter graph, so edge fades silenced entire clips.
- Cleaning could destroy a clip outright: spectral denoise can mistake a quiet,
  steady delivery for the noise it is removing. Loudness is now compared before
  and after and the clip reverts if too much was lost.
- Export numbering counted missing phrases, leaving gaps in the checklist.
- Synthesized clips were labelled as source media, because normalization rewrites
  every status to `final` before export reads it.

### Changed

- Step logic moved into a `waze_voice/` package; the per-step scripts remain as
  thin wrappers with their original flags.
- The phrase inventory was rebuilt against Waze's real prompt set. The previous
  list was invented and contained prompts Waze does not have.

## 0.1.0

- Initial scaffold: repository layout, phrase inventory, and a validator.
