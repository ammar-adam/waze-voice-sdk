## What this changes

<!-- One or two sentences. What was wrong, or what is new. -->

## Why

<!-- The reasoning, especially if the change is not obviously correct.
     If it fixes a bug, what was the failure mode? -->

## How it was verified

<!-- Delete what does not apply. -->

- [ ] `python tests/run_tests.py` passes
- [ ] `python -m ruff check waze_voice scripts tts tests` is clean
- [ ] `python -m mypy waze_voice` is clean
- [ ] Ran the pipeline end to end on real media
- [ ] Tested on a real device (please also open a device report)

## Checklist

- [ ] No audio, model weights, datasets, or media are included in this PR
- [ ] No copyrighted character, performer, or brand names in public-facing files
- [ ] New behaviour has a test, or there is a reason in the PR why it does not
- [ ] Docs updated if behaviour or flags changed

<!--
A note on audio changes: if this alters extraction, cleaning, normalization, or
the size budget, say what it does to the numbers. "Clips land within 0.1 LU" or
"pack utilisation went from 88% to 99%" is much easier to review than a diff.
-->
