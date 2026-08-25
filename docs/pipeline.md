# Pipeline design

How the six steps fit together, and why they are built the way they are.

## Shape

```
sources.csv ─┐
             ├─> extract ──> audio/extracted/  phrase__take1.wav
your media ──┘                     │
                                   v
                             clean ──────> audio/processed/    phrase__take1.wav
                                   │
   phrases.json ──> synth ─────────┼──────> audio/synthesized/ phrase.wav
   (gaps only)                     │
                                   v
                            normalize ────> audio/master/      phrase.mp3
                                   │
                          ┌────────┴────────┐
                          v                 v
                         qa              export ──> audio/export/
                     (audition)                       clips/
                                                      IMPORT_CHECKLIST.md
                                                      VERIFY-IMPORT-FIRST.md
                                                      pack-manifest.json
```

Two files carry state between steps:

- **`config/phrases.json`** is the contract. Every step reads it to know what the pack
  should contain. Normalization writes each phrase's `status` back so a fresh clone can
  see what is done.
- **`audio/build-manifest.json`** is the record of what actually happened: which take a
  clip came from, whether it was cut or synthesized, what loudness it measured before and
  after, which stages it passed through. Later steps read it instead of guessing. Export
  uses it to mark synthetic prompts in the checklist; validation uses it to flag loudness
  outliers. It is regenerated freely, and is Git-ignored.

## Why a library plus thin CLIs

Every step lives in `waze_voice/steps/` and is exposed twice: as a subcommand of
`wvs`, and as a standalone script in `scripts/`. Both call the same function.

The scaffold had six independent scripts, each with its own copy of "find the repo
root", "load phrases.json", "check for ffmpeg", and "find the clip for this phrase".
Four copies of a rule is four chances for them to disagree, and they had already
started to: the clip-matching logic differed between `normalize.py` and `clean.py`, so a
file one step produced was not necessarily a file the next step would find.

## Step notes

### extract

Validates the entire CSV, then checks every referenced media file exists, before running
any ffmpeg. A typo in row 40 fails immediately rather than after 39 successful cuts.

Cutting uses a coarse input-side seek followed by an `atrim` inside the filter graph.
Input seek is cheap on a two-hour file and lets a lossy decoder settle; the in-graph trim
makes the cut accurate. The tempting alternative, input `-ss` paired with an output-side
`-ss`/`-t`, is wrong: output seeking is applied *after* the filter graph, so a fade
positioned relative to the clip gets applied to the wrong part of the stream, and the
seek then selects a region the fade has already silenced. Silently. See
`waze_voice/media.py:cut`.

Clips get 20 ms fades at both edges so a hard cut does not click.

### clean

Three modes, because the right answer depends on the source and on what the user is
willing to install:

- `copy` for already-clean dialogue.
- `ffmpeg` (default) band-limits and applies spectral denoise. No PyTorch, runs in
  seconds, handles room tone and hiss.
- `demucs` runs real source separation and keeps the vocal stem. This is what rescues a
  line buried under a score.

Demucs is invoked **once for all clips**, not once per clip: the model loads on startup,
so a per-file loop pays that cost every time. Its output layout is
`<out>/<model>/<track>/vocals.wav` rather than flat files, so the step maps the results
back to phrase IDs explicitly instead of globbing.

Cleaning is guarded. Spectral denoise decides what counts as noise from the clip's own
content, and a quiet, steady delivery can look exactly like the noise it is removing. The
step measures loudness before and after; if the clip lost more than
`clean.max_loss_lu`, or went silent, the processed file is replaced with the original and
the revert is reported. A noisy prompt is recoverable, a silent one is not.

### synth

Fills phrases that have no audio anywhere. Default backend is Chatterbox zero-shot
cloning: it takes the user's own cleaned clips as a reference and speaks new lines in that
voice without any training run. A navigation pack yields well under a minute of usable
source audio, far below what fine-tuning needs and comfortably above what zero-shot
conditioning needs.

Chatterbox was chosen over XTTS-v2 and F5-TTS on licensing, not on quality or Python
support. Both alternatives ship weights restricted to non-commercial use, and in Coqui's
case the company that would have to grant a commercial licence no longer exists.
Chatterbox is MIT including its weights. For a project whose premise is "bring audio you
have the right to use", a default that silently caps every output at non-commercial would
be the wrong trade. Both alternatives remain selectable via `--backend`. See [tts.md](tts.md).

A backend is just a callable: speak this text, in this voice, to this file. Adding one
means writing a loader that returns such a callable, which keeps model-specific API
differences out of the step logic. Backend-specific generation knobs go through
`synth.generate_options` untouched, so a library renaming a parameter does not require a
change here.

Synthesis is optional throughout. `wvs run` checks availability first and skips the step
with one clear line rather than aborting the run, and any phrase left unfilled is carried
into the export checklist as a prompt to record manually.

### normalize

Measure, then apply one static gain. Not ffmpeg's single-pass `loudnorm`, which runs in
dynamic mode: it compresses to hit the target as it goes, which pumps on short material
and gives different results depending on where the speech sits in the clip.

The full order matters:

1. Trim leading and trailing silence.
2. Measure the trimmed length, then fade the new edges and add controlled padding.
3. Measure loudness of *that* file, shaped exactly as it will ship.
4. Apply the gain and a true-peak limiter, encode to MP3.
5. Re-measure, and if the result drifted more than 0.3 LU, correct once and re-render.

Steps 2 and 3 are in that order for a reason. Measuring before shaping lets padding and
fades move the result afterwards, which on a sub-second prompt is worth several LU. The
correction pass in step 5 covers MP3 encoding and limiter engagement.

On the fixture, this brings clips whose inputs span 16 dB to within 0.1 LU of each other.

### qa

Renders each route step as one continuous piece of audio. Real navigation chains "In 500
meters" onto "turn right" as a single instruction, then leaves a longer gap before the
next one. Playing eighteen clips alphabetically tells you almost nothing; hearing them
chained at driving pace is what surfaces the clip that is a beat too slow or lands at the
wrong emphasis.

Interactive by default, recording pass/fail per instruction into `audio/qa-report.json`.
`--render` writes the whole route to a file instead, optionally over a road-noise bed via
`--bed`, so you can listen on the car audio you will actually navigate with.

### export

Numbers only the clips that exist, so the checklist has no gaps to explain. Order comes
from each phrase's `group` and `order` fields rather than array position.

Writes the clips, `IMPORT_CHECKLIST.md`, `VERIFY-IMPORT-FIRST.md`, `pack-manifest.json`,
and a README. The manifest records `import_path_verified: false` and says why. See
[waze-import-workflow.md](waze-import-workflow.md).

## Take resolution

Which file represents a phrase is decided in one place, `waze_voice/takes.py`, searching
`processed` then `synthesized` then `extracted`.

Matching is exact. A prefix match would let the phrase `arrive` claim
`arrived__take1.wav`, and lexical sorting would put `take10` ahead of `take2`. Both
produce a finished pack that says the wrong thing with no error anywhere. The `__take`
separator exists to make the split unambiguous, and both cases are pinned by tests.

## Testing

```powershell
python tests\run_tests.py
```

`tests/fixtures.py` generates synthetic source media with ffmpeg: modulated tone bursts at
known timestamps, at deliberately different levels, optionally over a background bed. The
end-to-end test runs the real pipeline over it and checks the output audio, not just that
files appeared.

The bursts are modulated rather than pure tones on purpose. A steady sine looks exactly
like noise to a spectral denoiser, so an unmodulated fixture would test the cleaner
against a signal no real recording produces, and would pass while the real behaviour went
unchecked.

Tests needing ffmpeg skip cleanly when it is absent. The suite uses `unittest` from the
standard library, so it runs with nothing installed.
