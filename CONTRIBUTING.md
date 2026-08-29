# Contributing

## The most valuable contribution

**Tell us what happened on a real device.** Open a
[device report](../../issues/new?template=device-report.yml).

Waze does not document any of this. The filename list, the 0.8 MB size limit, and
the share-link flow are all things people worked out and wrote down. Negative
results count: "that directory does not exist on Android 15" saves the next
person the same twenty minutes.

If Waze's prompt list has changed, or a filename in
[`waze_voice/wazepack.py`](waze_voice/wazepack.py) turns out to be wrong, that is
the single most useful thing you can report.

## Setting up

```bash
git clone https://github.com/ammar-adam/waze-voice-sdk
cd waze-voice-sdk
python -m pip install -r requirements-dev.txt
python scripts/wvs.py doctor
python tests/run_tests.py
```

You need Python 3.10+ and ffmpeg. Nothing else: the core pipeline is standard
library only, and the tests generate their own audio, so a fresh clone can run
the full suite without any media of your own.

The optional extras (`requirements-clean.txt` for Demucs, `requirements-tts.txt`
for synthesis) each pull in PyTorch. You do not need either to work on the core
pipeline.

## Before opening a pull request

```bash
python tests/run_tests.py
python -m ruff check waze_voice scripts tts tests
python -m ruff format --check waze_voice scripts tts tests
python -m mypy --platform linux waze_voice
python -m mypy --platform win32 waze_voice
```

CI runs all five, plus the test suite on Windows and Linux across Python 3.10
to 3.13, plus an end-to-end pack build. Running them locally first is faster than
finding out from a red check.

`ruff format --check` is there so the tree stays in the formatter's shape.
Without it, the next person to run `ruff format` gets twenty files of unrelated
churn in their diff.

mypy runs twice because it narrows `sys.platform` to whichever platform it is
running on: a Windows-only branch reads as unreachable on Linux, and the CI
runner is Linux, so a single run only ever checks half the platform-specific
code. Prefer a plain `bool` constant over a direct `sys.platform` comparison
when a branch has to survive both.

mypy runs with `disallow_untyped_defs`, so a new function needs annotations.
That is not ceremony: switching it on found two functions returning `Any`
through a concrete annotation, and a handler being passed `None` for a
parameter typed as a config.

## What must never be committed

The repository ships **no audio, no model weights, no datasets, and no finished
packs**, and that is not negotiable. `.gitignore` is set up to make that the
default outcome, but it is not a substitute for looking at `git status` before
you push.

Also keep copyrighted character, performer, and brand names out of public-facing
files. The project is deliberately generic. See [LEGAL.md](LEGAL.md).

## House style

- **Explain the non-obvious in comments, not the obvious.** Several things in
  this codebase look wrong until you know why they are that way: the silence
  padding before loudness measurement, the `atrim` instead of an output-side
  `-ss`, bisection instead of the closed-form Lagrange multiplier. Each of those
  carries a comment saying what breaks otherwise. Match that.
- **Failure messages should say what to do.** `"ffmpeg not found"` is half an
  error message; the other half is the install command.
- **ASCII only in console output.** Windows terminals still default to a legacy
  code page in plenty of setups.
- **No new runtime dependencies in the core pipeline** without discussing it
  first. Being installable with nothing but Python and ffmpeg is a feature.
- Line length 100. `ruff` enforces the rest.

## Testing

The suite uses `unittest` from the standard library, so `python tests/run_tests.py`
needs nothing installed.

- `tests/test_inventory.py` and `tests/test_pack.py` are pure logic, no ffmpeg.
- `tests/test_pipeline.py` and `tests/test_synth.py` run real ffmpeg and skip
  cleanly when it is absent.
- `tests/fixtures.py` generates synthetic source media. If you need a different
  shape of pack to test something, add it there rather than committing audio.

**Test the audio, not just the file count.** A test that checks a file appeared
would have passed while a fade filter silenced every clip, and while Demucs was
dropping every phrase ID. Assert on duration, loudness, channel count, byte size
against the budget.

When you fix a bug, the test should fail without the fix. Several tests in here
carry a docstring explaining the bug they exist to catch; that is the format.

## Areas that could use help

- **Device reports.** See above.
- **The phrase inventory.** `config/phrases.json` covers all 43 prompts Waze
  recognises, but the labels and `tts_text` values are a starting point, not
  gospel.
- **Synthesis backends.** A backend is a callable that speaks text into a file;
  adding one means writing a loader that returns such a callable. See
  `waze_voice/steps/synth.py`.
- **The budget weights.** `weight` in `config/phrases.json` is a judgement call
  about how often each prompt is heard. Better numbers would improve every pack.
- **Non-English packs.** The pipeline is language-agnostic but nothing has
  exercised that.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
